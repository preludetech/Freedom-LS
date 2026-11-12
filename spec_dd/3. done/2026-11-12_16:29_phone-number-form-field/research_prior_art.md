# Research: prior art for phone number fields

Question: what has already been tried for phone number fields, here or elsewhere, and what happened?

## Here: what exists in the repo

### The `phone` question type exists and validates nothing

- `freedom_ls/form_engine/enums.py:24` defines `QuestionType.PHONE = "phone"`. Migration `freedom_ls/form_engine/migrations/0005_alter_formquestion_type.py` carries it in the choices. `freedom_ls/form_engine/schema.py:28` has `PHONE = "phone"` in the pydantic schema.
- `freedom_ls/form_engine/templates/form_engine/question.html:52-53` renders it as `<input type="tel" inputmode="tel">` through `form_engine/inputs/text_input.html`. Nothing else.
- `freedom_ls/form_engine/typed_answers.py:175-177` returns `None` (no error) for phone, with the comment "Real phone validation needs libphonenumber and a country, which is a different piece of work." Sibling types `email` and `url` use Django's `EmailValidator` and `URLValidator` in the same function, so a phone check slots in the same way (a branch returning an error string such as `You entered "x". Enter a valid ...`).
- `claude_plugins/fls-content/skills/content-types/resources/form-files.md:226-233` documents the phone question as "Renders a telephone input. The number itself is not format-validated." This doc will need updating.
- `docs/product/learner-experience.md:17` lists "a phone number" among form question types and says answers that do not fit the type are refused at submission. `docs/product` has nothing else on phone validation. A product doc change is needed once the field validates.
- No phone library is installed: no match for `phonenumber` in `pyproject.toml` or any `models.py`.

### Decisions already taken

1. **Spec `2026-09-17_15:28_form_engine data field`** (`spec_dd/3. done/2026-09-17_15:28_form_engine data field/idea.md:23-25`): deliberately shipped `phone` as a keyboard hint only. "Real phone validation means `libphonenumber` and a country, which is a different piece of work." That is the work this spec does.
2. Its research file (`.../research_form_builder_field_types.md`, section 5, around lines 186-205) concluded:
   - There is no country-agnostic phone regex that actually validates.
   - `django-phonenumber-field` wraps `python-phonenumbers` and needs `PHONENUMBER_DEFAULT_REGION` or an explicit country to parse a national-format number.
   - MDN says `type="tel"` enforces nothing.
   - Google Forms treats phone as short answer plus a regex rule. Typeform, JotForm and GOV.UK Forms treat phone as a first-class type.
   - It called a searchable country selector "future work", and said a plain `<select>` of about 195 entries is poor (GOV.UK, Baymard). Country as a question type was left out because it needs a maintained reference list (ISO 3166, translated, `django-countries`-style). The `dropdown` type "is not a solution to the country question".
   - Sources it cited: https://django-phonenumber-field.readthedocs.io/en/latest/phonenumbers.html, https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/tel, https://baymard.com/labs/country-selector, https://design-system.service.gov.uk/components/select
3. **Bug APP-1** (`spec_dd/2. in progress/downstream_bugs_oct_29/learner-ux-polish-from-mega-qa/idea.md:172-179`): a downstream application's phone question accepted "hello", showed it on check-your-answers and stored it. The interim fix proposed was "at least reject input with fewer than 7 digits until full validation lands". This spec is the "full validation". It is an open stopgap, so the two should not conflict: the stopgap should be dropped or subsumed when this lands. Check whether it was ever implemented, since `typed_answers.py` currently shows no digit check.

### Specs that depend on this one

- `spec_dd/1. next/roadmap.md:24,252-254`: `phone-number-form-field` is "in progress"; `multi-step-course-applications` is **blocked** by it (and by `file-scanning`).
- `spec_dd/1. next/multi-step-course-applications/idea.md:37,195-207`: it needs the field for the "ask for help" contact form (name, phone number, a good time to call, a question). Anonymous applicants have no `User`, so the number is a form answer hung off the `CourseApplication`, not a profile field. Nothing else in that idea constrains the field's shape. It does imply the field works for anonymous applicants, where there is no stored profile or organisation to supply a default country, which fits the decision to use the browser locale only.
- `spec_dd/1. next/corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md:111-115` and `.../idea.md:31` mention a `user-profile-upgrades` spec that "depends on `phone-number-form-field`" and adds phone and date of birth to the user profile. That directory is no longer under `spec_dd/` (no match for `user-profile-upgrades` in a glob). The same file says `phone-number-form-field` is "form-engine field only". Nothing in this repo currently plans a phone field on `User`. If one returns, it should reuse whatever this spec builds (validator, normalised storage) instead of making a second place for the same data. Do not build it here.

### Older phone data and a dropped field

- `spec_dd/3. done/2026-03-08_18:18_refactor-student-model/idea.md:9,59`: the old `Student.cellphone` field (with `id_number`, `date_of_birth`) was dropped entirely. There is no legacy phone column to migrate.
- `spec_dd/3. done/2026-05-05_08:18_better-registration/idea.md:33` said extra registration details such as phone number "should be configurable per site". The mechanism that shipped is `additional_registration_forms`. `claude_plugins/fls-dev/skills/registration/SKILL.md:182-200` shows a downstream example: `PhoneNumberForm` with `forms.CharField(max_length=20)` saving to a `user.phone_number` attribute on a downstream-owned model. That is plain free text, so downstream projects may already hold unvalidated numbers.
- Tracking specs (`server-side-conversion-tracking`, `tracking-pixels`, `google-analytics-setup`) all state that no phone number is sent to ad platforms. A normalised E.164 value must not change that.

### Existing data to watch

Existing `phone` answers are stored as free text in `text_answer`, with no format check. Downstream QA fixtures (`.claude/agent-memory/sdd-qa-data-helper/reference_application_forms_qa_baseline.md`, `freedom_ls/qa_helpers/management/commands/qa_create_dronex_demo.py` and similar) use phone questions. Old answers will not parse, so the spec must say what happens to a previously stored value when its form is reopened or rendered (display raw, do not re-validate stored rows).

## Elsewhere: libphonenumber lessons

Searched via web search. The sources are forum threads and changelogs, not official guarantees.

1. **Metadata ships with the library, so validity changes with upgrades.** `isValidNumber` uses metadata bundled at release time. When a numbering plan changes (a January 2026 thread reports new North American overlays), real numbers fail until the library is upgraded and redeployed. Source: https://groups.google.com/g/libphonenumber-discuss/c/d4WAHU39LeY. A second thread reports a real Australian 0492 mobile rejected because metadata lagged real allocations: https://groups.google.com/g/libphonenumber-discuss/c/DiGEeCWLQ8M.
2. **Release notes show validity rules tightening.** Some metadata updates make `isPossible` stricter, so numbers that passed earlier can fail: https://android.googlesource.com/platform/external/libphonenumber/+/refs/heads/android10-release/release_notes.txt. The Python port keeps its own changelog: https://sources.debian.org/src/python-phonenumbers/8.12.57-5/python/HISTORY.md.
3. **`django-phonenumber-field` hit this exact problem.** From 4.0.0 it stopped raising `ValueError` on save of an invalid number, because upstream validation changes can leave "invalid" numbers in the database. It flags them in `__str__` and `__repr__` instead. Earlier versions (2.4.0 onward) raised on invalid input, including inside queryset filters. Source: https://data.safetycli.com/changelogs/django-phonenumber-field.
4. **Lessons that follow (my inference, not quoted from the sources):**
   - Validate when the answer is submitted. Do not re-validate stored answers on read, edit or export, or an upgrade will break old rows.
   - Consider whether "possible" (a length and shape check) is enough, or whether the stricter "valid" check is worth the false-rejection risk. A strict check will reject some real people, and the cost here is an applicant who cannot submit a form.
   - Store the original input next to the normalised E.164 value, or at least be able to show what the person typed.
   - Pin the `phonenumbers` version through `uv.lock` and treat bumping it as a routine dependency update.
   - Parsing a national-format number needs a region. A number typed with a `+` prefix parses without one.
   - A free-text field cannot be migrated safely in bulk. Any backfill needs a path for rows that fail to parse (leave as is, flag), never a destructive rewrite.
5. **Country selector prior art** (already collected in the research file above): a plain 195-entry `<select>` is poor usability (https://baymard.com/blog/drop-down-usability, https://design-system.service.gov.uk/components/select). A searchable control is the better answer. The idea file says "don't overcomplicate things", so the spec should decide how much of this to take on.
6. **Locale-based default** (answers.md): the `Accept-Language` region (en-ZA to +27) is a hint, not a fact. Browsers often send `en-US` or a bare `en` with no region. The spec must say which fallback applies, and the answers already decided: no preselected country.

## Gaps

- Not checked: whether APP-1's 7-digit stopgap was implemented (no sign of it in `typed_answers.py`).
- Not fetched: the official libphonenumber FAQ (`FAQ.md` returned 404 at the URL tried). The libphonenumber findings above come from search results and changelogs.
- `docs/product/` has no other mention of phone number beyond `learner-experience.md:17`.

status: ok · reason: repo search of spec_dd, docs and code done; web lessons from search snippets, official FAQ not fetched
