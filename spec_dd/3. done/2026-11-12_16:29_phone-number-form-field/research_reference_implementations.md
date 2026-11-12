# Research: reference implementations of a phone number field with country picker

Topic: `reference_implementations`. Context: the idea wants a phone number field in the form engine, with country code and proper validation. Answers so far: default country comes from the browser locale only (Accept-Language region), with no preselection when there is no region. There is no organisation or site setting.

## Summary

- Every serious implementation stores the number as E.164 (`+27821234567`) and validates it with a Google libphonenumber port. That library carries the country metadata.
- Two UI patterns exist. One is a single `tel` input that accepts national or international format, with a region used to interpret national numbers. The other is a country `<select>` plus a number input.
- Validation is only as current as the bundled metadata. Strict validity checks go stale, so some authors recommend a looser "possible number" length check.
- Defaults are almost always a caller-supplied country code (a setting). Auto-detection is by IP lookup, which the answers file rules out. Reading the browser locale server-side is not a pattern in these libraries, so FLS would write that bit itself.

## django-phonenumber-field (Python and Django server side)

Docs: https://django-phonenumber-field.readthedocs.io/en/latest/reference.html

- **Storage:** the model field is a `CharField` subclass. `PHONENUMBER_DB_FORMAT` defaults to `E164`. Storing national format makes data depend on `PHONENUMBER_DEFAULT_REGION`, and changing that region later can corrupt stored data. Formats without extension support drop extensions for good.
- **`RegionalPhoneNumberWidget`:** the default form widget. It renders `<input type="tel">` and shows the value in national format for the field's `region`. Without a region, a user must type an international number (`+...`). There is no country picker. The region comes from the `region` argument or `PHONENUMBER_DEFAULT_REGION` (default `None`), so the default is a setting and not detected.
- **`SplitPhoneNumberField`:** a `MultiValueField` made of a country `<select>` and a `tel` input (`PhoneNumberPrefixWidget`). It needs Babel for localized country names. It is the closest match to "country code plus number". It has overridable `prefix_field()`, `number_field()` and `invalid_error_message()` hooks.
- **Error text:** the validator code is `invalid`. The default message reads "Enter a valid phone number (e.g. (506) 234-5678) or a number with an international call prefix." `SplitPhoneNumberField` can put a region-specific `{example_number}` into the message, which reads well.
- **Dependencies:** the `phonenumbers` Python package, which is libphonenumber's port and ships its metadata. Babel is needed for the split field. There is no JS dependency, so there are no flags and no search in the picker. The `<select>` is plain HTML.

## intl-tel-input (JS widget)

Repo: https://github.com/jackocnr/intl-tel-input. Options docs: https://intl-tel-input.com/docs/options. Licence MIT.

- **Storage:** the widget gives you a number from its API. It is normally read as E.164 and posted from a hidden input or on submit. It does not own storage.
- **Country choice and default:** the user picks from a flag dropdown, with search. `initialCountry` is an ISO2 code. Auto-detection is `initialCountryLookup` (renamed from `geoIpLookup`). It is a caller-supplied Promise, usually an IP geolocation service such as ipapi, and only runs when `initialCountry` is unset. With no initial country, the input starts in a "globe" state. `countryOrder` (replaces `preferredCountries`) puts chosen countries first. `onlyCountries` and `excludeCountries` restrict the list. `separateDialCode` is `true` by default, so the dial code sits beside the input and cannot be deleted. If the user types a different dial code, the list opens.
- **Validation:** client-side only, through the "utils" module, which is libphonenumber compiled for the browser. It gives validity and error types, and `strictMode` (default `true`) blocks non-digits and over-length input. The server must re-validate, because the widget is only a UI check.
- **Size and dependencies:** the utils module is about 260 KB and loads lazily via `loadUtils`, after the window `load` event. The docs give no core size. Flags come from flag-icons and the country list from mledoze's countries project. Core has zero dependencies. Validation and strict mode do not work until utils has loaded.
- **Framework support:** vanilla JS plus React, Vue, Angular and Svelte wrappers. Vanilla JS is the relevant one for HTMX and Alpine.

## react-phone-number-input (React, built on libphonenumber-js)

Repo: https://github.com/catamphetamine/react-phone-number-input

- **Storage:** E.164 string. An empty field gives `undefined`.
- **Country choice and default:** the "with country select" component has a flag dropdown. `defaultCountry` (a two-letter code) sets the initial selection and the national-format parsing. With neither `country` nor `defaultCountry`, only international input is allowed. The library does no detection. The README suggests the caller supplies the default.
- **Validation:** `isPossiblePhoneNumber()` (length only) and `isValidPhoneNumber()` (digits checked, looser on the default metadata). The author recommends the "possible" check, because strict validation rejects newly assigned ranges once metadata is stale.
- **Metadata and size:** libphonenumber-js metadata comes in `min` (about 80 KB, default), `max` (about 145 KB, strict checks and number types), `mobile` (about 95 KB) and `custom` (only chosen countries).

## Form builders

- **Jotform:** the Phone element has a Country Code toggle that adds a code field beside the number, with a Default Country setting. There is also an International Telephone Picker widget (intl-tel-input style) with its own Default Country. A user thread says the default preselects the dropdown but does not prefill the number input. Both are builder-set defaults. https://www.jotform.com/help/how-to-add-and-set-up-the-phone-element-on-your-form/ , https://www.jotform.com/help/how-to-add-and-set-up-the-international-telephone-picker-widget-on-your-form
- **Tally:** a phone number block that shows the international format by default, with a country code dropdown the respondent can use or type into. The display shows the number length for the chosen country. The help page documents no default-country setting. https://tally.so/help/phone-number
- **Typeform:** a community post says the desktop version offers a country code list. A feature-request thread claims it uses geo rules for the default country, which is unverified. I found no official page. https://community.typeform.com/build-your-typeform-7/country-code-telephone-number-1044
- **Google Forms:** no phone field. It offers regex validation on a text question, so there is no country picker and no metadata. https://www.jotform.com/google-forms/google-form-phone-number-validation (a competitor's description).
- **Moodle and other LMSs:** I did not find a source for Moodle. Its core profile fields use a plain text `phone1`/`phone2` with no validation or country picker (from memory, not verified). Treat this as a gap if the spec depends on it.

## Comparison

| Implementation | Stores | Country chosen by | Default country | Validation | Extra weight |
|---|---|---|---|---|---|
| django-phonenumber-field Regional | E.164 | typed `+` prefix or fixed region | `PHONENUMBER_DEFAULT_REGION` setting | server, `phonenumbers` | Python only |
| django-phonenumber-field Split | E.164 | `<select>` | per field region | server, `phonenumbers`, region example in error | Python plus Babel |
| intl-tel-input | E.164 via API | flag dropdown with search | `initialCountry` or caller lookup (IP) | browser utils, about 260 KB lazy | JS, flags, utils |
| react-phone-number-input | E.164 | flag dropdown | `defaultCountry` prop | `isPossible` or `isValid`, 80 to 145 KB | React, libphonenumber-js |
| Jotform, Tally | form-specific | dropdown | builder setting | built in | hosted |

## Implications for FLS (observations, not decisions)

- Store E.164 in the form attempt's answer. The form engine's answers are probably text, so a string fits. That avoids needing a region to read it back.
- The server must validate in all cases, since client widgets are only a convenience. `phonenumbers` (or `phonenumberslite`, which drops the geocoder and carrier data) is the standard server-side choice. `django-phonenumber-field` wraps it and supplies a `SplitPhoneNumberField` with a country `<select>`. Check whether it fits the form engine's field model before adding it.
- A plain `<select>` plus `tel` input with no JS matches "don't overcomplicate" and the Django, HTMX and Alpine stack. intl-tel-input adds flags, search and a roughly 260 KB lazy module, so it is optional polish.
- The locale default needs custom code. Parse the region out of Accept-Language (`en-ZA` gives `ZA`) and preselect it only when it is a supported country. None of the references do this, and all of them leave the unselected state to the user. An example in the error message ("e.g. 082 123 4567") would help users, and the `{example_number}` pattern shows how.
- A trap to design for: a region-less national number cannot be interpreted. The field should require a country, or an international `+` number.

## Sources

- https://django-phonenumber-field.readthedocs.io/en/latest/reference.html
- https://github.com/jackocnr/intl-tel-input
- https://intl-tel-input.com/docs/
- https://intl-tel-input.com/docs/options
- https://github.com/catamphetamine/react-phone-number-input
- https://www.jotform.com/help/how-to-add-and-set-up-the-phone-element-on-your-form/
- https://www.jotform.com/help/how-to-add-and-set-up-the-international-telephone-picker-widget-on-your-form
- https://tally.so/help/phone-number
- https://community.typeform.com/build-your-typeform-7/country-code-telephone-number-1044
- https://www.jotform.com/google-forms/google-form-phone-number-validation

status: ok · reason: all requested references covered; Moodle and Typeform default behaviour unverified (noted in the file)
