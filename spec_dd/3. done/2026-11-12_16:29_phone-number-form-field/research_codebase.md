# Research: codebase (phone-number-form-field)

Question: what in the existing codebase does adding a phone number field to the form engine touch, reuse or conflict with?

Fixed by the user (answers.md): the default country comes only from the browser locale (the region in Accept-Language, en-ZA -> +27). No site or organisation setting. No region in the locale means no country preselected.

## Headline

A `phone` question type already exists end to end. It is a plain `<input type="tel">` that stores whatever the person typed in `QuestionAnswer.text_answer` and validates nothing. This work upgrades an existing type (country selection, real validation, a normalised stored form), not a new type. `typed_answers.answer_error` says so itself: "phone, short_text, long_text: nothing to check. Real phone validation needs libphonenumber and a country, which is a different piece of work." (`freedom_ls/form_engine/typed_answers.py`, last branch of `answer_error`.)

There is no phone or country handling anywhere else in production code, and no phone library in `pyproject.toml` (checked for phonenumbers, django-phonenumber-field, libphone, intl-tel, country: no hits in `pyproject.toml`, `package.json`, `uv.lock`).

## 1. Where the `phone` type is defined today

Every place the string `phone` / `QuestionType.PHONE` appears:

- `freedom_ls/form_engine/enums.py`: `QuestionType.PHONE = "phone", _("Phone")` (Django `TextChoices`, backs `FormQuestion.type`). `PHONE` is in `FREE_TEXT_QUESTION_TYPES`, so phone answers are text-only (no `QuestionOption` rows).
- `freedom_ls/form_engine/schema.py`: pydantic `QuestionType(StrEnum)` with `PHONE = "phone"`; `FormQuestion.type` Field description lists the types as a string ("... email, url, phone, dropdown").
- `freedom_ls/form_engine/templates/form_engine/question.html`: `{% elif question.type == "phone" %}` includes `form_engine/inputs/text_input.html` with `input_type="tel" input_mode="tel"`.
- `claude_plugins/fls-content/validate/schema.py`: bundled copy of the schema (line 104 `PHONE = "phone"`, line 1225 description string).
- `claude_plugins/fls-content/validate/tests/test_validator.py` (~line 835): parametrised list of types including `"phone"`.
- `claude_plugins/fls-content/skills/content-types/resources/form-files.md`: field table (line 119) and "Phone question example" (line 226) which says "Renders a telephone input. The number itself is not format-validated." That sentence becomes wrong.
- `demo_content/functionality_demo_application_form/1. about-you.yaml`: the only demo/authored use (`question: What is your phone number?`, `required: false`, `type: phone`). Existing authored forms use bare `type: phone` with no other keys, so the change must keep that valid.
- `freedom_ls/accounts/tests/test_forms.py:243` has a "phone" parametrised string; unrelated check, not a form-engine hit.

Migrations: `FormQuestion.type` is a choices CharField; `migrations/0005_alter_formquestion_type.py` and `0002` show type-choice changes have needed `makemigrations`. Adding a new `QuestionType` member (if the spec adds one rather than reusing `phone`) needs a new migration; reusing `phone` needs none. New per-question settings would be new `FormQuestion` columns, like `min`, `max` (`0006`) and `decimal_places` (`0007`).

## 2. How question types are modelled (pattern to follow)

Three parallel definitions that must agree:

1. Django model enum `freedom_ls/form_engine/enums.py` (`QuestionType`, `FREE_TEXT_QUESTION_TYPES`, `OPTION_QUESTION_TYPES`). Kept free of model imports on purpose (`scoring` and `submissions` import it).
2. Pydantic schema `freedom_ls/form_engine/schema.py`: `FormQuestion(BaseBaseContentModel, content_type=ContentType.FORM_QUESTION)`, `extra="forbid"` style (a field in YAML needs a matching schema field and model column). Per-type options are plain optional fields (`min`, `max`, `decimal_places`), validated in `FormQuestion.validate_bounds` via the shared `typed_answers.question_bounds_error`, which `FormQuestion.clean()` (models.py, admin route) also calls. Note `question_bounds_error` rejects `min`/`max` on any type other than date, time, number, and `decimal_places` on non-number: any new phone setting (for example an allowed-countries list) needs the same shared-function treatment so YAML and admin agree.
3. The content_base registry: `FormQuestion`, `FormContent`, `FormPage`, `Form` register via `content_type=ContentType.X` class keyword (`freedom_ls/content_base/schema.py`). Adding a phone setting does not touch the registry; only adding a new content type would.

Content sync: `content_save` writes pydantic fields to model columns (uuid written back to the file). Any new field on the pydantic `FormQuestion` must have a model field with the same name.

The fls-content authoring plugin carries a **bundled copy** of the schema: `claude_plugins/fls-content/validate/schema.py` header says it bundles four sources (`content_base/schema.py`, `content_engine/schema.py`, `form_engine/schema.py`, `form_engine/typed_answers.py`) and is re-synced with `/update_claude_plugin_fls_content`. Lines ~1023-1029 note the `parsed_date` ... `question_bounds_error` block is a verbatim copy of `typed_answers.py`. So changing `typed_answers.py` (where phone validation would live) forces a re-sync of that bundle, including a hard problem: the validator plugin cannot import Django, so a phone-aware validation (needing the `phonenumbers` library) must not leak into the bundled authoring-time check; only schema-level rules (field names, allowed values) should be mirrored. This is a plugin-generic constraint: the plugin stays generic (CLAUDE.md), but fls-content is the FLS content authoring plugin and already mirrors FLS schemas.

## 3. Answer storage, validation, marking, display

Storage: `QuestionAnswer.text_answer = models.TextField(blank=True, default="")` (`freedom_ls/form_engine/models.py:724`). One string per answer; no structured storage. A phone answer stored as one normalised string (E.164, e.g. `+27821234567`) fits without a migration. Storing country separately would need a new column. Existing rows hold whatever was typed (e.g. `082 123 4567`), which cannot be turned into E.164 without a country, so display and export must tolerate unparseable legacy values (this is the pattern `format_answer` already states: "Returns the raw string unchanged when it will not parse").

Save and validate flow:
- `FormProgress.save_answers(questions, post_data)` (models.py ~391): for each question, `has_submitted_answer` (`submissions.py`) decides if there is an answer (free-text: non-blank trimmed `question_<id>` value), then for `FREE_TEXT_QUESTION_TYPES` calls `submitted_text_answer` (reads `post_data["question_<id>"]`, strips) and `typed_answers.answer_error(question, text)`. A non-None message yields `RejectedAnswer(text, message)`, nothing is written, and the old row is kept.
- Consequence for the design: the POST contract is one field `question_<id>` per free-text question. A country picker plus national-number input means either (a) JS combines them into one `question_<id>` value (E.164) before submit, or (b) a second POST key (e.g. `question_<id>_country`) is read in `submitted_text_answer`/`save_answers`, which is a change to the shared submission code. With no JavaScript, option (b) or a typed `+27...` full number is the only route. `has_submitted_answer` would then count a submission that has only a country selected and an empty number as unanswered, which is the right behaviour for a preselected country (it must not make an otherwise-empty optional phone question "answered").
- `answer_error` messages follow the form `You entered "<text>". Enter ...`; the phone branch should match (naming the value and the format). It returns None for empty-after-strip never being called (blank is handled earlier).
- Re-render on rejection: `text_input.html` re-fills `value="{{ rejected.text }}"` from `RejectedAnswer.text`; the rejected message is shown under the input in `question.html` (`aria-invalid`, `aria-describedby=question_<id>_error`, HTTP 422 convention for HTMX validation errors per CLAUDE.md). A country-aware widget has to hand back both the typed number and the chosen country on rejection; `RejectedAnswer` carries only `text`.
- Other consumers of `save_answers`: the learner course form page (`learner_interface/templates/learner_interface/course_form_page.html`, with `form_engine/partials/answer_errors.html`) and the course-applications form page (`course_applications/templates/course_applications/form_page.html`). Both render questions through `form_engine/partials/page_children.html` -> `form_engine/question.html`, so one template change covers both.

Marking/scoring: phone is unmarked. `scoring.py` and the QUIZ/CATEGORY_VALUE_SUM strategies work on option rows; `FREE_TEXT_QUESTION_TYPES` are skipped (e.g. `reports/gather.py:516` `build_confusion_block` skips free-text types; `reports/indexes.py:625,689` likewise). No marking change is needed.

Display to educators and reviewers:
- `freedom_ls/form_engine/templatetags/form_engine_tags.py`: filter `answer_display` -> `typed_answers.format_answer(question_type, text_answer)`. Today it formats only DATE and TIME and returns the raw string otherwise. This is the single hook for showing a stored E.164 value in a readable international form (e.g. `+27 82 123 4567`); the same function must stay tolerant of unparseable legacy values.
- Used by `freedom_ls/form_engine/templates/admin/form_engine/_answers.html:18` (admin answers view) and `course_applications/templates/course_applications/check_your_answers.html:66` (applicant check-your-answers).
- `freedom_ls/form_engine/admin.py:478` `QuestionAnswerAdmin` display method uses `format_answer(...)[:50]`.
- Note `format_answer` imports only `enums` and `django.utils` (module docstring: never `models`). The phone library import would be new, but it does not touch models, so the constraint holds.

## 4. Reports and CSV exports

- `freedom_ls/form_engine/exports.py`: `answer_value(answer)` returns `answer.text_answer or None` for free-text types (line 167); `answer_cell` produces the spreadsheet cell. Docstring: dates and times stay as stored ISO text because "a sheet parses that where it would not parse the locale-formatted display text". The same logic argues for exporting phone as the stored E.164 string, not the formatted display.
- Consumer: `freedom_ls/course_applications/resources.py` `_answer_cell` (django-import-export resource for applications) calls `answer_cell`.
- **Conflict: CSV formula safety.** E.164 values start with `+`. `freedom_ls/base/csv_safety.py` `FORMULA_TRIGGERS` includes `"+"`, and `escape_csv_formula` prefixes `'` to any cell starting with a trigger. It is applied in `site_aware_models/admin_exports.py` (`FormulaSafeCSV`), `panel_framework/tables.py:217`, and `base/csv_import.py` (template/error CSVs). So a phone cell exported through these paths becomes `'+27821234567` in the sheet. Check which path the application export takes (the import-export resource is likely wrapped by `FormulaSafeCSV`). Options for the spec: accept the leading apostrophe (safe, slightly ugly, and a recent done spec `2026-11-09_06:18_csv-formula-extra-triggers` deliberately widened this), or export a form without a leading `+` (e.g. digits with country code); the safety rule must not be weakened for one column. This is the most real conflict found.
- Reports: phone is free text, excluded from option-based confusion/tally logic; no change expected in `freedom_ls/reports/`.

## 5. How existing field types render (cotton, HTMX, Alpine)

- Server-rendered Django templates, not cotton, for the form engine inputs: `form_engine/question.html` dispatches by `question.type` to `form_engine/inputs/{text_input,long_text,dropdown,multiple_choice,checkboxes,file_upload}.html`. `text_input.html` is generic: `<input type="{{ input_type }}" inputmode=... id=question_<id> name=question_<id>>`, with `min`/`max`/`step`, `required`, `disabled` when `read_only`, `aria-invalid`, and value from `rejected.text` else `existing_answers[question.id].text_answer` (via `get_dict_item` from `fls_base_filters`). A `<c-callout>` cotton component is used only for the unhandled-type error.
- `dropdown.html` is the only existing `<select>` and is option-model driven (`QuestionOption` rows); it cannot be reused for countries directly because countries are not authored options, but its markup and classes are the styling reference. Input classes (`rounded-md border border-border-input bg-white px-3 py-2 ... focus:ring-primary`) repeat across `text_input.html` and `course_applications/partials/applicant_details_field.html` (the latter comments that it deliberately copies them).
- The question is a `<fieldset>` with a `<legend>`; label for the input is `sr-only` (`<label class="sr-only" for="question_<id>">`). A composite country + number control must keep one accessible label, probably the legend plus a second label for the country select, and one error id (`question_<id>_error`).
- Alpine: CSP build, "every component registered with Alpine.data(), directives reference method or property names only, zero inline expressions" (`freedom_ls/form_engine/static/form_engine/js/alpine-components.js`, today only `questionFileUpload`, used from `file_upload.html` with `x-data="questionFileUpload"`). A country widget needs a new `Alpine.data(...)` component in that file, no inline expressions. That script is loaded with `<script defer src="{% static 'form_engine/js/alpine-components.js' %}">` in `course_applications/templates/course_applications/form_page.html:7`; learner pages load `learner_interface/js/alpine-components.js` (`_exam_runner_base.html`, `_course_base.html`), and `course_form_page.html` references an `examRunnerForm` component. **Check that every page that renders `question.html` also loads `form_engine/js/alpine-components.js`**: only the applications `form_page.html` is confirmed to; the learner course form page and the admin do not obviously do so for `questionFileUpload` today (file upload may only be on applications). A phone control must degrade without JS (plain tel input accepting a `+` number) if it cannot be assumed loaded everywhere.
- HTMX 2.x and Alpine plugins load from `cdn.jsdelivr.net` (`_base.html`, per comment in `config/settings_base.py` near `SECURE_CSP_REPORT_ONLY`). CSP is `SECURE_CSP_REPORT_ONLY` (report-only) with `script-src` allowing self, unsafe-inline and cdn.jsdelivr.net, so a client library (e.g. intl-tel-input) from jsdelivr or static would pass; there is no npm runtime-JS pipeline for libraries beyond Tailwind (`npm run tailwind_build`).
- HTMX: forms post whole pages (CSRF via body `hx-headers`); validation errors return 422 (CLAUDE.md, `claude_plugins/fls-dev/resources/templates_and_cotton.md`).
- `read_only` renders `disabled` inputs; a composite control must also honour it (a disabled field is not submitted, which is fine as read-only sittings never save).

## 6. Existing phone or country handling elsewhere

- Production code: none. No phone/country field on `accounts.User` (checked by grep); `SiteSignupPolicy.additional_registration_forms` (a list of dotted paths to downstream Django forms) is the extension point for collecting extra profile data, and the registration skill documents an example `PhoneNumberForm` with `forms.CharField(max_length=20, label="Phone Number")` writing `user.phone_number` (`claude_plugins/fls-dev/skills/registration/SKILL.md:182-200`). That is downstream example code, not FLS behaviour. Test fixtures `freedom_ls/accounts/tests/_completion_view_fixtures.PhoneNumberForm` and `STORED_PHONE_NUMBERS` and the `qa_create_incomplete_registration_learner` command use it; the QA command says "there is no production registration form shipped".
- The course-applications "applicant details" step (`course_applications/templates/course_applications/applicant_details.html`, `partials/applicant_details_field.html`) is a plain Django form (first/last name, email) with text inputs; it does not use form-engine questions, so it will not pick up the new phone control unless separately wired. Out of scope unless the spec says otherwise.
- Roadmap context (`spec_dd/1. next/roadmap.md`): `multi-step-course-applications` is **blocked by** this spec, and `user-profile-upgrades` (phone number on the user profile) depends on `phone-number-form-field` (per `spec_dd/1. next/corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md:111-115`, which also says this spec is "form-engine field only"). So reusable pieces (a validation function and a country-aware widget) are better exposed as importable code, not buried in the form engine; but CLAUDE.md says do not build what was not requested, so the spec should only name the seam.
- `babel>=2.18.0` is already a dependency (used in `content_engine/prices.py` for currency and `content_engine/checks.py` for `Locale`/`UnknownLocaleError`). Babel's `Locale.parse("en-ZA", sep="-")`/`.territory` and `babel.core.parse_locale` give the region from a language tag, and `Locale.territories` gives localised country names. No `phonenumbers` / `django-phonenumber-field` yet, so the validation library is the one new dependency (add via `uv add`). `phonenumbers` offers `region_code_for_country_code` / `country_code_for_region` and `SUPPORTED_REGIONS` for the picker.

## 7. How the locale reaches render time

- `config/settings_base.py`: `LANGUAGE_CODE = "en-us"`, `USE_I18N = True`. `MIDDLEWARE` has **no** `django.middleware.locale.LocaleMiddleware` (list at settings_base.py:167-186), so `request.LANGUAGE_CODE` is the fixed setting, the active language is always `en-us`, and Django does not parse Accept-Language itself. grep for `Accept-Language`, `get_language`, `translation.` in `freedom_ls/`: no hits.
- Therefore the region must be read directly from `request.META["HTTP_ACCEPT_LANGUAGE"]` (or `request.headers["Accept-Language"]`). Django offers `django.utils.translation.trans_real.parse_accept_lang_header` (semi-private) which returns `(tag, q)` tuples; or use Babel (`babel.core.negotiate_locale` / `Locale.parse`) to pull the territory from the highest-quality tag that carries a region. Must handle: no header, `*`, tags without a region (`en`, `fr`), invalid tags (Babel raises `ValueError`/`UnknownLocaleError`: be specific per CLAUDE.md), and region codes that are not dialling regions (`001`, `419`, `EU`). First tag with a region wins vs. highest-q tag with a region is a spec decision.
- Do not add `LocaleMiddleware` for this: it would change the active language for the whole site (translation of templates, date formats via `formats.date_format` in `format_answer`), which is far outside this feature.
- Reachability in templates: `question.html` and `text_input.html` are included with the page context; `django.template.context_processors.request` presence is not verified here (a `csp` context processor is at settings_base.py:222). The view contexts for `course_form_page.html`, `course_applications/form_page.html` and the HTMX fragment re-renders (`page_children.html`) all would need the default region computed once and passed (or a template tag/filter reading `request`), and `form_engine/templates/admin/form_engine/_answers.html` renders answers, not inputs, so it does not need it. Views are in `freedom_ls/form_engine/views.py` and the two consumer apps.
- The locale is a hint only: someone filling the form on a shared or abroad browser; the picker must let them change it. Preselecting only when a region exists, and never persisting the guess, matches the user's decision.
- Pages rendered in `read_only` / review of already-stored answers: the stored E.164 carries its own country, so the stored country wins over the locale; the locale default applies only to an empty answer.

## 8. Tests that will move

- `freedom_ls/form_engine/tests/test_typed_answers.py` (answer_error/format_answer cases, likely including a "phone is not validated" case), `test_schema.py`, `test_models.py`, `test_views.py`, `test_exports.py`, `tests/templatetags/test_form_engine_tags.py`.
- `claude_plugins/fls-content/validate/tests/test_validator.py` if schema fields are added.
- `freedom_ls/course_applications` tests rendering the demo form; `demo_content` tests that load `functionality_demo_application_form` (the existing bare `type: phone` must keep validating).
- Playwright tests exist for the form engine (`form_engine/tests/playwright/`), so a JS-driven control would want one.

## 9. Docs to update (generic vs FLS rule)

- `claude_plugins/fls-content/skills/content-types/resources/form-files.md`: field table row for `type`, new optional keys if any, and the "Phone question example" sentence "The number itself is not format-validated" (line 228). Also the plugin's bundled `validate/schema.py` re-sync.
- `claude_plugins/fls-dev` skills for the form engine (the domain glossary entry for form question types and any form-engine skill): not read in detail; the researcher for docs should grep for `short_text` in `claude_plugins/fls-dev` and `docs/` before the plan.
- `demo_content/functionality_demo_application_form/1. about-you.yaml` is the demo to extend, per "demo_content — Course content demonstrating all course functionality".
- Plugins stay generic: nothing in `claude_plugins/django-stack`, `sdd` or `productivity` should name this.

## Key conflicts and decisions for the spec

1. Existing `phone` type, no new enum member needed; legacy answers are unvalidated free text, so display, export and re-edit must tolerate non-E.164 values.
2. Submission contract is one `question_<id>` string; composite country + number needs either JS composing E.164 or a second POST key, and `RejectedAnswer` carries only `text`.
3. CSV formula escaping (`base/csv_safety.py`, `+` trigger) will prefix `'` to E.164 values in exports.
4. No `LocaleMiddleware`; the region must be parsed from the Accept-Language header by hand (Babel already installed), with the no-region case meaning no preselection.
5. New Python dependency `phonenumbers` (not present); client-side library optional; Alpine is the CSP build, so any component goes in `form_engine/static/form_engine/js/alpine-components.js` with no inline expressions, and it must also load on every page that renders `question.html`.
6. Bundled schema copy in `claude_plugins/fls-content/validate/schema.py` needs re-sync, and authoring docs in `form-files.md` need the phone sentence fixed.
7. Not touched: marking and scoring, report tallies, the content_base registry, site/organisation settings (none, by decision), the course-applications applicant-details step (a separate plain Django form).

Reference URLs: none used; all findings are from the repository.

status: ok · reason: complete
