# Research: UX patterns for a phone number input with a country code

Topic `ux_patterns`, for the `phone-number-form-field` spec. Context from `answers.md`: the default country comes from the browser locale only (Accept-Language region, e.g. en-ZA -> +27); when there is no region, no country is preselected. No IP geolocation, no site or organisation setting.

Confidence notes: GOV.UK, Evil Martians, Baymard (explain-phone-number-field, input masking, drop-down usability) and intl-tel-input docs were read or summarised via search. Items marked "unverified" or "from general knowledge" were not confirmed against a fetched page.

## 1. Country select beside a national-number input vs one input that accepts "+"

- **Two controls (country picker + national number)** is the dominant pattern in libraries (intl-tel-input, react-phone-number-input) and in Evil Martians' guide. Their recommendation: either require strict E.164 in one field, or know the country first and accept the rest in any format. For international collection they recommend a separate country-code control. Source: https://evilmartians.com/chronicles/phone-inputs-and-you-the-designers-essential-ui-guide
- **Single free-text input** is what GOV.UK recommends for UK-centred services: accept spaces, hyphens, brackets, country and area codes, with a hint such as "For international numbers include the country code". It also says more research is needed on international numbers. Source: https://design-system.service.gov.uk/patterns/telephone-numbers/
- **Trade-off:** a single input depends on the user knowing to type "+" and the code; a picker makes the code explicit and gives the validator a region. Baymard notes users often type numbers in formats other than the hinted one, and in the US/Canada the "1" or "+1" is usually omitted and including it often causes errors. So the national input should tolerate a pasted "+27 ..." number. Source: https://baymard.com/research-articles/input-masking-form-field
- Evil Martians: keep the entered number when the user changes the country; cap length at 16 digits (E.164 max is 15) to allow for autofill edge cases.
- **Implication for FLS:** with a locale-derived default that is sometimes empty, the two-control pattern fits: the picker is either preselected or visibly empty ("Select country"), and a number pasted with a leading "+" can be parsed to set the country.

## 2. What the picker shows: flags vs names vs dial codes

- Common library layout: flag + dial code in the closed control, flag + country name + dial code in the open list (intl-tel-input; from general knowledge).
- Evil Martians suggests a "Country - Code" list sorted alphabetically by country name. Flags were not covered by it.
- Flags alone are an accessibility and recognition problem: they are not text, many flags are similar, and flags stand for countries not languages or regions. The country control needs a text name for screen readers (see section 7). The intl-tel-input accessibility docs imply the country needs a text name. Source: https://intl-tel-input.pages.dev/docs/accessibility
- A flag is a decoration; the country name must always be present in the list, and the dial code is the useful part for people who know it.
- Dial codes are ambiguous on their own: +1 covers the US, Canada and several Caribbean nations; +7 covers Russia and Kazakhstan. The list must show the country name, and the selected country (not only the code) must be stored or derivable.

## 3. Searching a ~240-country list: native select vs combobox

- Evil Martians: the list is just under 200 countries, so users need a shortcut: type-to-search, or at least press the first letter to jump. Source: link above.
- Baymard's drop-down research: for fields like country selection, where validation matters, a well-performing alternative to a drop-down is an autocomplete field. Source: https://baymard.com/research-articles/drop-down-usability (via search snippet, content not fetched)
- Native `<select>`: free keyboard and mobile support, best accessibility baseline, but type-ahead only matches the beginning of the visible text (so "United States" is found by "U", and "USA" or "+27" are not found), and rows cannot hold much rich content (flags are emoji or nothing).
- Combobox/searchable list (intl-tel-input with search enabled): filters on typing; needs ARIA and a live region announcing result count. Libraries that skip this have been reported to change country silently for screen reader users (a WCAG 4.1.3 status-message problem). Source: https://gitlab.com/catamphetamine/react-phone-number-input/-/issues/119
- Reasonable middle ground (general knowledge): a native `<select>` with option text like "South Africa (+27)" works without JavaScript, and enhancement to a combobox is optional. A Digital Thrive article attributes to Baymard a native select with JS autocomplete enhancement; unverified against Baymard's pages. Source: https://www.digitalthriveai.com/en-ca/resources/web-design/redesigning-the-country-selector/

## 4. Formatting: as you type vs on blur

- GOV.UK: avoid input masking and placeholder values, which make a number harder to type or check. Avoid reformatting numbers after entry; some users were confused by it. Source: https://design-system.service.gov.uk/patterns/telephone-numbers/
- Baymard (input masking): masks are risky because users enter formats other than the one expected; a mask that depends on the selected country is one suggested approach. Source: https://baymard.com/research-articles/input-masking-form-field
- Evil Martians: show a placeholder with the expected format after a country is selected; auto-format when the country is known.
- Pattern summary: the conservative choice is to accept anything, strip separators for storage, and not rewrite the user's text. As-you-type formatting (libphonenumber AsYouType) is a library feature and a source of caret-position bugs.
- If formatting is done at all, do it on blur or only on the read-only display, never while the user is mid-edit.

## 5. Validation: where errors appear and when

- GOV.UK: validate with Google's libphonenumber so users can fix mistakes. Error text appears in the Error message component, above the input and linked with `aria-describedby`. Messages:
  - empty: "Enter a UK phone number"
  - wrong format, no example shown: "Enter a phone number, like 01632 960 001, 07700 900 982 or +44 808 157 0192"
  - wrong format, example shown: "Enter a phone number in the correct format"
  Source: https://design-system.service.gov.uk/patterns/telephone-numbers/
- GOV.UK's general pattern is to validate on submit and show an error summary plus an inline message. Inline-on-blur validation is acceptable but should not fire while the user is still typing (general knowledge; not verified on the fetched page).
- intl-tel-input: the library can validate but presenting errors accessibly is the integrator's job. Source: https://intl-tel-input.pages.dev/docs/accessibility
- Error placement for a two-part field: one error message under the whole group, tied to the national-number input; say which part is wrong when possible (no country chosen vs number invalid for that country).
- In FLS, HTTP 422 for HTMX validation errors applies (project convention), so server-side re-render is the natural place for errors.
- Baymard: if the field is required and its purpose is unclear, users give false data or abandon; add a short explanation or mark it optional. Source: https://baymard.com/blog/explain-phone-number-field

## 6. Mobile keyboards and autofill

- `type="tel"` on the national-number input (GOV.UK). Source: https://design-system.service.gov.uk/patterns/telephone-numbers/
- `autocomplete="tel"` lets the browser autofill the full international number; GOV.UK says it is needed for WCAG 2.2 criterion 1.3.5 in production. Note the interaction with a split design: `tel` fills a full "+27 82 ..." number, so the national-number input should accept that and set the country from it. The alternatives `tel-national` and `tel-country-code` exist for split fields (from general knowledge; HTML autofill spec, not fetched).
- `inputmode="tel"` is not mentioned by GOV.UK. `type="tel"` already brings up the phone keypad on mobile; `inputmode="tel"` is redundant on a `type="tel"` input (general knowledge) and matters only if a different input type is used.
- The tel keypad on some phones has no "+" key, which is a reason for a separate country picker rather than relying on the user typing "+".
- Evil Martians: browser autofill can trim long numbers, so let the user review and correct. Source: https://evilmartians.com/chronicles/phone-inputs-and-you-the-designers-essential-ui-guide

## 7. Screen-reader labelling of the two parts

- The national-number input still needs its own accessible name, ideally a visible `<label for>`; `aria-label`/`aria-labelledby` is the fallback. The injected country UI does not replace this. Source: https://intl-tel-input.pages.dev/docs/accessibility
- The country control needs its own accessible name (for example "Country code" or "Country"), otherwise a screen reader announces only "combo box" or "menu". A native `<select>` without a label fails WCAG (select-name). Source: https://getwcag.com/accessibility-guide/select-name
- Group both under `<fieldset>`/`<legend>` (the question text) or `role="group"` with `aria-labelledby`, with the hint and error linked through `aria-describedby` (general knowledge, consistent with GOV.UK's pattern).
- A custom picker button should expose `aria-expanded`, `aria-haspopup`, `aria-controls`, and a polite live region announcing the number of search results. Source: https://www.pkgstats.com/pkg:vue-a11y-phone (via search snippet).
- Selecting a country should be announced or at least visible as text; changes that happen silently fail WCAG 4.1.3. Source: https://gitlab.com/catamphetamine/react-phone-number-input/-/issues/119
- Flags must be hidden from the accessibility tree (`aria-hidden`) with the country name provided as text.

## 8. Read-only display of the answer

- No authoritative source found for this; recommendations from general practice:
  - Show the number in international format with the "+" (e.g. "+27 82 123 4567"), as one text string, optionally with the country name nearby. International format is unambiguous without needing the flag.
  - Do not use a flag-only display.
  - GOV.UK warns against styling numbers as `tel:` links on devices that can't make calls, so if links are added, do it deliberately. Source: https://design-system.service.gov.uk/patterns/telephone-numbers/
  - Stored value: E.164 is the usual canonical form (Evil Martians recommends E.164 as the strict format); the display form is derived from it at render time, so reformatting never alters what the user typed in storage.

## Summary of takeaways for the spec

1. Two controls (country picker + national number) with tolerance for a pasted "+CC" number; picker preselected from locale region, otherwise visibly empty.
2. Picker text includes country name and dial code; flags optional and decorative only.
3. Native `<select>` is the lowest-risk start (labelled, type-ahead for names); a combobox is an enhancement and brings ARIA/live-region cost.
4. Do not mask or reformat while typing; validate server-side with libphonenumber; one error message for the group, linked with `aria-describedby`.
5. `type="tel"` plus `autocomplete="tel"` (or the split `tel-national`/`tel-country-code` tokens); `inputmode` redundant.
6. Visible label on the number, a separate accessible name on the country control, fieldset/legend around both.
7. Store E.164; display read-only answers as international format text.

## Sources

- https://design-system.service.gov.uk/patterns/telephone-numbers/
- https://evilmartians.com/chronicles/phone-inputs-and-you-the-designers-essential-ui-guide
- https://baymard.com/blog/explain-phone-number-field
- https://baymard.com/research-articles/input-masking-form-field
- https://baymard.com/research-articles/drop-down-usability
- https://intl-tel-input.pages.dev/docs/accessibility
- https://gitlab.com/catamphetamine/react-phone-number-input/-/issues/119
- https://www.pkgstats.com/pkg:vue-a11y-phone
- https://getwcag.com/accessibility-guide/select-name
- https://www.digitalthriveai.com/en-ca/resources/web-design/redesigning-the-country-selector/

status: ok · reason: complete; some points flagged as general knowledge or unverified
