# Research: known complaints about phone number fields

Question: what do users commonly complain about with phone number fields in web forms?

Method note: two rounds of web search (summaries, not full page reads). Several items below are leads from search snippets and were not verified on the source page. Each is tagged `confirmed-in-snippet` or `lead`.

## Complaints, by theme

### 1. Valid numbers rejected (stale metadata, new ranges)
- An active Australian 0492 mobile number was flagged invalid by libphonenumber. The thread points to out-of-date metadata. Fix path: upgrade the Python `phonenumbers` package, or the library bundling its own metadata. (confirmed-in-snippet) https://groups.google.com/g/libphonenumber-discuss/c/DiGEeCWLQ8M
- django-phonenumber-field's 4.0.0 changelog says it cannot completely prevent invalid numbers entering the system, and that validation changes in upstream `phonenumbers` are one way invalid numbers end up stored. So stored data can go stale as metadata changes. (confirmed-in-snippet) https://data.safetycli.com/changelogs/django-phonenumber-field
- intl-tel-input expects callers to validate (`isValidNumber`) before submit. The maintainer's issue template says to check the validation demo first. (lead) https://cdn.jsdelivr.net/gh/jackocnr/intl-tel-input@master/README.md
- Implication: validation is only as fresh as the pinned library version. Keep the dependency upgradeable, and prefer rejecting clearly impossible numbers over strictly rejecting unrecognised-but-plausible ones. (This is an inference, not a source claim.)

### 2. Wrong country preselected
- ClickUp: the phone field always defaults to US (+1), with no way to change the default, so every respondent scrolls to their country. https://feedback.clickup.com/feature-requests/p/allow-default-country-code-selection-for-phone-number-field-in-forms
- Typeform community: request that the country selector follow the user's location. https://community.typeform.com/build-your-typeform-7/update-the-country-selector-of-the-phone-field-based-on-user-location-8474
- Writesonic: auto-detecting country from the first digits typed misfires. US users with area code 248 got switched to another country. https://feedback.writesonic.com/bs-feature-requests
- An intl-tel-input write-up describes a New Zealand user autofilling a national-format number without noticing the wrong country was selected, and submitting a wrong number. (confirmed-in-snippet; via https://socket.dev/npm/package/intl-tel-input/overview/19.5.4)
- Locale and IP guesses fail for travellers and expats (general knowledge, no source found in this pass). The project has already chosen browser locale only (answers.md), so the preselect will sometimes be wrong. The field must make the selected country obvious and easy to change, and an empty selection must be handled when the locale has no region.

### 3. Leading 0 and country code doubling
- libphonenumber FAQ: the trunk prefix (leading 0) is usually stripped on parse, but kept for some countries (e.g. Italy) because it is part of the dialled number. Code that strips or adds a 0 by hand will be wrong for some countries. https://chromium.googlesource.com/external/libphonenumber/+/master/FAQ.md
- A "+49 0921..." style number (0 after the country code) is accepted by lenient parsing. A maintainer said the strict E.164 form is invalid and suggested checking that the formatted result reproduces the input. https://groups.google.com/g/libphonenumber-discuss/c/_6JAx1gAn1o
- WebKit: autofill of a telephone number into a text/tel input removes the leading 0 (first two phone fields in a form). A browser bug, so not preventable by us, but it shows national-format input can arrive mangled. https://bugs.webkit.org/show_bug.cgi?id=173917
- Implication: let libphonenumber parse with the selected country as region, store E.164, and never concatenate "+code" onto a user-typed string by hand. (inference)

### 4. Input masks fighting paste and autofill
- intl-tel-input removed format-as-you-type in v8.0.0 (issue #346 on jackocnr/intl-tel-input), so libraries have moved away from live masking. (lead; version/issue number from search summary) https://cdn.jsdelivr.net/gh/jackocnr/intl-tel-input@master/README.md
- Drupal report: Chrome autofill let invalid values be submitted, bypassing the widget's checks. (lead) https://www.drupal.org/node/3034377
- Implication: validate on the server regardless of any client widget, and do not rely on a mask. Accept pasted text with spaces, dashes, parentheses and a leading "+".

### 5. Country lists
- Evil Martians: keep the typed number when the user changes the country, do not clear it. https://evilmartians.com/chronicles/phone-inputs-and-you-the-designers-essential-ui-guide
- Same write-up covers flag-only selectors and long lists (it argues for showing country names and dial codes and supporting type-ahead search). Not verified past the snippet.
- Singapore government's OUI component puts the default country at the top of the dropdown. https://oui.open.gov.sg/docs/components/phone-number-field

### 6. Errors that do not say what is wrong
- No source found in this pass for a specific complaint. General guidance (inference): distinguish "missing", "not a valid number for <country>", and "too short/too long", rather than one generic "invalid phone number".

### 7. Numbers reformatted unexpectedly
- No source found in this pass. Related: the libphonenumber FAQ above on stripping or keeping the leading 0 means display and stored forms differ. Keep one canonical stored form (E.164) and decide display format explicitly. (inference)

## Gaps
- No direct jackocnr/intl-tel-input or django-phonenumber-field GitHub issue pages were fetched. The search tool returned only aggregators. A follow-up could fetch the repo issue lists.
- Nothing found on "falsehoods programmers believe about phone numbers" or on libphonenumber new-range rejections beyond the Australian thread.

## Takeaways for the spec
1. Validate server-side with an up-to-date libphonenumber binding. Plan for dependency upgrades.
2. Country default is a convenience only. Make the chosen country visible and changeable, preserve typed digits when it changes, and handle no default.
3. Parse with the selected country as region and store E.164. Never hand-concatenate prefixes or strip zeros.
4. No input mask. Accept messy pasted and autofilled input.
5. Specific error messages.

status: ok · reason: web research completed with limits noted (snippet-level sources, no direct GitHub issue pages)
