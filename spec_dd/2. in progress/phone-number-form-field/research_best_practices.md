# Research: best practices for international phone number collection and validation (Python/Django)

Constraint from `answers.md`: the default country comes from the browser locale only (region in Accept-Language). No site or organisation setting. No region in the locale means no country preselected.

Note: written from established knowledge of the cited sources; URLs were not re-fetched in this run. Version-specific claims (django-phonenumber-field release numbers) should be checked at spec time.

## 1. Storage format: E.164

- Store the canonical E.164 string: `+` then country code then national significant number, digits only, max 15 digits (e.g. `+27821234567`). It is unambiguous, globally unique and what SMS/voice providers expect.
- E.164 does not carry formatting, the trunk 0 or the extension. Format for display at render time (`PhoneNumberFormat.INTERNATIONAL` or `NATIONAL` for the viewer's region).
- Do not store the user's raw string as the source of truth. If audit of what was typed is wanted, that is a separate decision (and extra PII).
- Extensions are not part of E.164; see section 5.
- Refs: https://www.itu.int/rec/T-REC-E.164 , https://github.com/google/libphonenumber/blob/master/FALSEHOODS.md

## 2. Validation with `phonenumbers` (libphonenumber port)

- `phonenumbers.parse(text, region)` raises `NumberParseException` (specific exception type to catch, in line with project rules). Then check validity.
- `is_possible_number` checks length only (cheap, lenient). `is_valid_number` checks length and prefix patterns against the country's numbering plan. Best practice: require `is_valid_number` for acceptance; do not accept merely possible numbers, but be aware validity can lag reality.
- Metadata freshness: numbering plans change (new mobile prefixes etc.). Valid new ranges get rejected if the library is old. Mitigation: keep `phonenumbers` updated (it releases frequently, mirrors upstream metadata), pin a minimum version, and let dependency updates carry it. Google's own guidance is to not over-trust validity for rejecting users in rarely-updated deployments; a lenient fallback (possible-number) is a policy choice to call out in the spec.
- `phonenumbers` is pure Python, no native dependency. `phonenumbers.carrier`/`geocoder` data is a separate large optional package set; not needed.
- Do not do "line type" restrictions (mobile only) unless a requirement exists; type detection is less reliable than validity.
- Do not validate with hand-written regexes.
- Refs: https://github.com/daviddrysdale/python-phonenumbers , https://pypi.org/project/phonenumbers/ , https://github.com/google/libphonenumber , https://github.com/google/libphonenumber/blob/master/FALSEHOODS.md

## 3. django-phonenumber-field

- Provides `PhoneNumberField` (model), a form field, widgets, and a `PhoneNumber` value object, built on `phonenumbers` (or optionally `phonenumberslite`). Stores E.164 by default in the DB; settings: `PHONENUMBER_DEFAULT_REGION`, `PHONENUMBER_DEFAULT_FORMAT`, `PHONENUMBER_DB_FORMAT`.
- The form field accepts a `region=` argument used to parse national-format input. Validation uses `is_valid_number`.
- Provides an optional `PhoneNumberPrefixWidget` (country select plus national number input), which fits "country code plus rest of number" UX; it needs a country choices list.
- Relevance to this project: the form engine stores answers generically (not as per-field model columns), so the model field is likely unusable there; the useful pieces are the form field/validation logic, or just using `phonenumbers` directly. A spec decision: new dependency (django-phonenumber-field) versus direct `phonenumbers` use. Either way `phonenumbers` is the dependency doing the real work.
- Refs: https://django-phonenumber-field.readthedocs.io/ , https://github.com/stefanfoulis/django-phonenumber-field

## 4. Parsing pasted numbers: leading + and trunk 0

- If input starts with `+`, parse with region `None`: the country code in the string wins and the selected region is irrelevant. If the user pasted `+27 82 123 4567` while the select shows another country, the pasted international form should win (or the country select should update to match); do not silently reinterpret it as a national number.
- National input (no +): parse with the selected country as region. The national trunk prefix (the leading 0 in many countries, e.g. 082... in South Africa, 07... in the UK) is stripped by libphonenumber's national-prefix rules for that region. So `082 123 4567` with ZA gives `+27821234567`. Do not strip the 0 by hand (some countries, e.g. Italy, keep a leading 0 as part of the number).
- Also handle `00` international call prefix: libphonenumber handles it only with the right region (the region's international prefix); safe route is to parse with the selected region.
- Typed `+` plus selected country conflict, and users entering the country code twice (`+27 +27...`), are the common edge cases; test them.
- Accept and tolerate spaces, dashes, brackets, dots; normalise by parsing, never by rejecting punctuation.
- Ref: https://github.com/google/libphonenumber/blob/master/FALSEHOODS.md , https://github.com/google/libphonenumber/blob/master/resources/phonenumber.proto

## 5. Extensions

- libphonenumber parses `ext.`, `x`, `;ext=` etc. into `PhoneNumber.extension`, and E.164 drops it. If extensions are not a requirement, do not offer one (the project rule: don't build what is not requested). Decide explicitly: either reject/ignore extensions, or store as RFC 3966 (`tel:+1-555-0100;ext=123`) / separate field. Silent dropping of a typed extension is a data-loss surprise, so the spec should say which.
- Refs: https://www.rfc-editor.org/rfc/rfc3966 , https://github.com/daviddrysdale/python-phonenumbers

## 6. Deriving a region from Accept-Language

- Django: `request.META["HTTP_ACCEPT_LANGUAGE"]`. Header is a q-weighted list, e.g. `en-ZA,en;q=0.9,af;q=0.8`. Parse by splitting on commas, ordering by q (default 1), and taking the first tag that has a region subtag. Django has `django.utils.translation.trans_real.parse_accept_lang_header` (semi-internal; stable but private module) returning `(tag, q)` tuples sorted by q. Writing a short parser is also fine.
- Region subtag: second subtag of two ASCII letters (`en-ZA` gives `ZA`), or a 3-digit UN M.49 code (`es-419`, not a country; ignore). Handle script subtags (`zh-Hant-TW`: region is the last 2-letter subtag, not the second). Uppercase it.
- Validate the region against `phonenumbers.SUPPORTED_REGIONS` (and `phonenumbers.country_code_for_region(region) != 0`) before preselecting; unknown or non-geographic (`001`) gives no preselection, as the user decided.
- Policy: should only the first (highest q) tag count, or the first tag with a region? Bare `en` with no region gives nothing; deciding whether to scan later tags (`en, en-ZA;q=0.8`) is a spec decision. Scanning is more helpful but may pick a language the user ranks lower; simplest defensible rule is the first region-bearing tag by q order.
- The locale reflects language preference, not location (an `en-US` browser used in South Africa preselects US); the user must be able to change the selection easily. Never lock the country.
- Do not use `LANGUAGE_CODE`/active Django language for this: it is usually a bare language, not the browser's region. Consider caching nothing; compute per request. Client-side alternative: `navigator.language` (same source, but server-side keeps non-JS render correct and testable).
- Refs: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language , https://www.rfc-editor.org/rfc/rfc9110#name-accept-language , https://www.rfc-editor.org/info/bcp47 , https://docs.djangoproject.com/en/stable/topics/i18n/ , https://docs.djangoproject.com/en/stable/ref/request-response/#django.http.HttpRequest.META

## 7. UX and accessibility

- One visible `<label>` associated with the number input (`for`/`id`); the country select needs its own accessible name ("Country calling code" / "Country"), not just a flag. Group the two controls (`role="group"` with `aria-labelledby`, or `<fieldset>`/`<legend>`) so the pair is announced as one question.
- Number input: `type="tel"`, `autocomplete="tel"` (full number incl. country code) or `tel-national` when the country is separate and the input holds only the national part; `autocomplete="tel-country-code"` for a separate code field. Choose consistently with what is submitted. `inputmode="tel"` brings the phone keypad on mobile (`type="tel"` already implies it; adding it is harmless). Do not use `type="number"` (strips leading zeros, spinner, no `+`).
- Country select options: show country name plus `+code`, in the user's language, searchable by typing (native `<select>` supports type-ahead; custom comboboxes need full ARIA combobox keyboard support, so prefer native select). Do not rely on flag emoji alone (screen readers and Windows render poorly).
- Do not restrict typed characters or enforce a mask that fights paste. Accept pasted international numbers (section 4).
- Errors: associated with the input via `aria-describedby`, plain language ("Enter a valid phone number for South Africa"), not just colour; HTMX validation errors return 422 per project convention.
- Do not require a specific format in the label; show an example for the selected country if cheap (`phonenumbers.example_number(region)`), as a hint not placeholder-only.
- Refs: https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/autocomplete , https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/inputmode , https://www.w3.org/WAI/WCAG22/Understanding/identify-input-purpose.html , https://www.w3.org/WAI/tutorials/forms/grouping/ , https://www.w3.org/WAI/tutorials/forms/instructions/ , https://design-system.service.gov.uk/patterns/telephone-numbers/ , https://baymard.com/blog/form-field-usability-phone-number

## 8. Privacy

- A phone number is personal information (POPIA, GDPR and similar apply; FLS has South African roots, so POPIA is relevant). Collect only if the form asks for it; tell the learner why.
- Do not log phone numbers (project rule: no logging added anyway), do not put them in URLs/query strings (GET), error messages, analytics or exception reports. Mask in admin/list views where full values are not needed.
- Use POST only; HTMX CSRF per project convention. The Accept-Language-derived default is request-local and not stored; do not persist the inferred region (it is inferred data about the person).
- Only the validated, normalised number is stored; avoid keeping raw input too. Include the field in any data export/deletion paths the project has for learner data.
- Do not verify by calling/SMS as part of this field; verification is a separate feature.
- Refs: https://www.gdprinfo.eu/ (general) , https://popia.co.za/ , https://owasp.org/www-project-top-ten/ , https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

## Summary of decisions the spec should take

1. Store E.164; format at display time.
2. Accept only `is_valid_number`; keep `phonenumbers` up to date (minimum version pin).
3. `phonenumbers` directly vs django-phonenumber-field (model field probably unusable in the form engine's generic answer storage).
4. `+` input overrides selected country; national input parsed with selected country; never hand-strip the trunk 0.
5. Extensions: explicitly out of scope (and say what happens if typed) unless a requirement appears.
6. Region from first region-bearing Accept-Language tag in q order, validated against supported regions; otherwise no preselection; always user-changeable.
7. Native select plus `type="tel"`, `autocomplete="tel-national"` (or `tel` if single input), labelled group, accessible errors.
8. Treat as PII: POST only, no logging, store normalised value only.

status: ok · reason: complete; URLs cited from established knowledge, not re-fetched
