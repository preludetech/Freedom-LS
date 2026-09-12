# Research: native `<input type="date/time/datetime-local">` for form_engine question types

Scope: browser support and rendering, UX/accessibility complaints, design-system positions,
`min`/`max`/`step` semantics, `datetime-local` timezone implications, and value pre-fill formats —
for the proposed `date`, `time`, `datetime` `QuestionType`s and `min`/`max` bounds on `FormQuestion`.

## What this settles (concrete, actionable findings)

1. **Support is fine, rendering is not uniform.** All three types (`date`, `time`, `datetime-local`) are
   supported in current Chrome, Edge, Firefox, Safari (desktop and iOS), Samsung Internet and Android
   Chrome. `datetime-local` reached "widely available" status across major browsers in October 2021.
   Nothing here blocks shipping. But **the widget the learner sees is different per browser/OS**: Chrome
   desktop shows a calendar-grid popup; Firefox desktop's is a plainer calendar; Safari desktop (older
   versions) fell back to a text box with no picker at all; iOS Safari shows the native wheel/reel picker
   (or a calendar view on iOS 14+); Android shows the Android Material calendar. There is no way to make
   these look the same, and no way to CSS-style the popup itself. — [caniuse: date](https://caniuse.com/mdn-html_elements_input_type_date), [Chrome dev blog FAQ](https://developer.chrome.com/blog/quick-faqs-on-input-type-date-in-google-chrome), [quirksmode](https://www.quirksmode.org/blog/archives/2017/02/making_input_ty.html)

2. **The wire value is always fixed-format regardless of what the user sees.** `date` → `YYYY-MM-DD`;
   `time` → `HH:mm` (or `HH:mm:ss` if seconds are in play); `datetime-local` → `YYYY-MM-DDTHH:mm` (no
   seconds by default, no timezone offset ever). This is also exactly the format required in the `value`
   attribute for pre-filling a saved answer back into the input — see §6. — [MDN: input/date](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/date), [MDN: input/time](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/time), [MDN: input/datetime-local](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/datetime-local)

3. **`min`/`max` are real HTML constraints but are trivially bypassable client-side**, and must be
   enforced again in `FormQuestion`/answer validation server-side regardless of whether the input renders
   them. They do **not** reliably help the "date of birth" scrolling problem — see finding 4.

4. **The date-of-birth / historical-date problem is real and well documented.** Native date pickers open
   showing the current month/year; a user entering a birth date has to click back potentially decades.
   Setting `max` to today does not change where the calendar opens. This is the single most consistent
   UX complaint found in the research, and it is the specific reason the GOV.UK Design System (and
   others following it) rejected the native date input for memorable/known dates. — [quirksmode](https://www.quirksmode.org/blog/archives/2017/02/making_input_ty.html), [GOV.UK Design System: Date input](https://design-system.service.gov.uk/components/date-input)

5. **GOV.UK is not an outlier — it is the model others copied.** NHS Digital Service Manual and other
   UK public-sector design systems explicitly follow GOV.UK's three-separate-text-inputs pattern for the
   same reason (known/memorable dates like DOB). USWDS (US) independently arrived at the same pattern
   ("memorable date": three labelled text inputs, no `<select>`s) for the same use case, while reserving
   a calendar-style picker for scheduling use cases where seeing days-of-week/availability matters.
   Shopify Polaris (a commercial product design system, not government) is the odd one out in scope: its
   "date picker" is for scheduling/report-filtering contexts and it explicitly says "always give users
   the option to enter the date using a text field as well" alongside the calendar — i.e. even Polaris
   does not treat the calendar widget alone as sufficient. — [GOV.UK Design System: Date input](https://design-system.service.gov.uk/components/date-input), [NHS service manual: Date input](https://service-manual.nhs.uk/design-system/components/date-input), [USWDS: Memorable date](https://designsystem.digital.gov/components/memorable-date/), [USWDS: Date picker](https://designsystem.digital.gov/components/date-picker/), [Shopify Polaris: Date picker](https://polaris.shopify.com/components/date-picker)

6. **Net design-system consensus for form_engine's use case (course application DOB, quiz dates a
   learner already knows) leans against a bare native date input**, per the government design systems
   researched. None of the sources found recommend `<input type="date">` for a known/memorable date; all
   recommend it be reserved (if used at all) for cases where a calendar view genuinely helps (scheduling,
   picking a future date, seeing day-of-week). This is a design-system **opinion** backed by their own
   user research, not a browser limitation — the idea author should decide whether form_engine's date
   questions are closer to "DOB/known date" (favours GOV.UK-style separate fields, more work) or "pick a
   date from a calendar" (favours the native input, far less work) on a case-by-case basis.

7. **Accessibility problems with native date/time inputs are real and inconsistent across AT**, not
   hypothetical: JAWS+Chrome doesn't announce browser validation errors; VoiceOver/iOS doesn't voice
   errors for out-of-range values; TalkBack/Android doesn't announce the current value unless the
   calendar is open; Dragon NaturallySpeaking (voice control) cannot interact with the control at all;
   default/error text often renders in raw `yyyy-mm-dd` rather than a locale-friendly format. No WCAG
   success criterion specifically bans native date inputs, and W3C's own ARIA Authoring Practices assume
   a *custom* combobox+dialog date picker pattern (not the plain native input) when a calendar affordance
   is wanted — implying the accessible calendar-picker pattern is more elaborate than `<input type=date>`
   alone provides. — [Hassell Inclusion: Is input type="date" ready for use in accessible websites?](https://hassellinclusion.com/blog/input-type-date-ready-for-use/), [W3C WAI-ARIA APG: Date Picker Dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/datepicker-dialog/)

8. **`datetime-local` carries no timezone information at all**, ever — this is by design, not a bug to
   work around. For a Django project with `USE_TZ = True`, a submitted value like `2026-09-12T14:30`
   is just a naive wall-clock string with no indication of which timezone it was entered in. The
   realistic options (trade-offs, not a recommendation) are set out in §5 below.

## 1–2. Browser/mobile support and rendering differences

- Desktop: Chrome, Edge and Opera render a full calendar-grid + up/down spinner picker for `date`,
  `time`, and `datetime-local`. Firefox renders its own, visually different but functionally similar,
  picker (marked "partial" on caniuse historically, but functional since Firefox 57 for `date`/`time`
  and widely available for `datetime-local` since ~2021). Safari on macOS has historically had the
  weakest support — older Safari versions rendered these as plain text boxes with no calendar affordance
  at all and displayed any pre-filled/default value in raw ISO format, which is confusing to users;
  Safari 14.1+ added a picker. — [caniuse: input-datetime](https://caniuse.com/mdn-html_elements_input_type_date), [LambdaTest: HTML Date Input](https://www.lambdatest.com/web-technologies/input-datetime), [Hassell Inclusion](https://hassellinclusion.com/blog/input-type-date-ready-for-use/)
- Mobile: iOS Safari uses the native iOS date/time picker — a three-reel spinner pre-iOS 13/14, moving
  to a calendar-tile view from iOS 13/14 onward for `date`. Android (Chrome, Samsung Internet, and other
  Chromium-based browsers) uses the Android Material calendar dialog for `date` and a clock-face dialog
  for `time`. Every later Samsung Internet release tracks Chromium, so it matches Chrome's picker exactly.
  There is currently no cross-platform way to unify or CSS-style these popups. — [quirksmode / Medium (Koch)](https://medium.com/samsung-internet-dev/making-input-type-date-complicated-a544fd27c45a), [Apple developer forums: iOS date picker min/max](https://developer.apple.com/forums/thread/743096)
- Practical implication for FLS: a learner filling in a `date` question on an iPhone, an Android phone,
  and a desktop Firefox browser will see three genuinely different-looking controls, all producing the
  same `YYYY-MM-DD` string. This is expected/acceptable native-input behaviour, not a bug to fix, but
  worth setting expectations about in the spec (no pixel-identical cross-device design is possible).

## 3–4. UX complaints, failure modes, min/max/step semantics

**Known complaints:**
- **DOB scrolling problem** (see finding 4): calendar always opens at "now", not near `max`. The only
  mitigation found is client-side JS to pre-set a sensible default `value` (e.g. 18 years before today)
  — this does not come from the `min`/`max` attributes themselves. — [quirksmode](https://www.quirksmode.org/blog/archives/2017/02/making_input_ty.html)
- **Locale-dependent *display* order vs. fixed wire value**: the on-screen field order (DD/MM/YYYY vs
  MM/DD/YYYY vs YYYY-MM-DD) is derived from OS/browser locale settings, entirely outside the page
  author's control ("there currently is no standard to specify the format" — Chrome dev blog). The
  `value` the server receives is always `YYYY-MM-DD` regardless of display order, so this is a
  user-facing-confusion risk, not a data-integrity risk.
- **Keyboard entry / partial or ambiguous entry**: users can type into date subfields; some browsers
  (Firefox, Edge per Hassell Inclusion's testing) allowed constructing invalid dates via keyboard that
  then get silently clamped or rejected inconsistently.
- **Paste behaviour**: not separately documented in sources found; native date inputs generally do not
  support pasting an arbitrary free-text date string into the composite control the way a plain text
  input would, since the control is subfield-based rather than a single text buffer. Not verified against
  a specific citation — flagged as an open point rather than a settled fact.
- **Safari-specific default-value confusion**: Safari (older/macOS) showed default/pre-filled values in
  raw unlocalized ISO format when it had no real picker, confusing users. — [Hassell Inclusion](https://hassellinclusion.com/blog/input-type-date-ready-for-use/)

**`min` / `max` / `step` — mechanics (MDN, verified per type):**

| Type | `min`/`max` format | `step` unit | `step` default | Notes |
|---|---|---|---|---|
| `date` | `YYYY-MM-DD` | days (as ms: step × 86,400,000) | 1 | step base = `min` if set, else `value`, else 1970-01-01 |
| `time` | `HH:mm` (or `HH:mm:ss`) | seconds (as ms: step × 1000) | 60 (1 minute) | non-multiple-of-60 step reveals a seconds field in the UI |
| `datetime-local` | `YYYY-MM-DDTHH:mm` | seconds (as ms: step × 1000) | 60 (1 minute) | `max` must be ≥ `min`; Safari's picker "will appear to allow any date/time but the value will be clamped to the valid range when a date is selected" |
| `number` (existing) | plain number | plain number | 1 | already implemented in FLS |

If `min`/`max` are not parseable as a valid date/time string in the required format, the browser applies
no constraint at all (fails silently/open, not closed). — [MDN: min attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/min), [MDN: step attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/step), [MDN: input/datetime-local](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/datetime-local)

**Explicit bypass warning:** `min`/`max`/`step` are client-side hints enforced by the browser's own UI/
validation only. They are trivially bypassed by disabling JS, editing the DOM, or simply POSTing a
crafted value directly (curl, HTMX intercepted, etc.). Server-side validation in `form_engine`'s answer
handling must independently enforce any bounds regardless of what is set on the `<input>`. This is a
general HTML forms fact, not specific to date/time types, but worth restating because the idea proposes
`min`/`max` as if they were sufficient validation.

**Does `max` affect where the picker opens?** No — confirmed by quirksmode's testing and Apple's own
developer forum threads reporting that iOS/iPadOS pickers "ignore" the min/max range when first opening.
`min`/`max` constrain what can be *selected/submitted*, they do not change the *initial displayed month/
year* of the calendar. — [quirksmode](https://www.quirksmode.org/blog/archives/2017/02/making_input_ty.html), [Apple dev forums](https://developer.apple.com/forums/thread/743096)

## 5. `datetime-local` and timezones — options and trade-offs

`datetime-local`'s value is, by spec, a naive local date+time with **no** timezone/offset component ever
sent to the server (confirmed: MDN explicitly notes "the input allows any valid combination of year,
month, day, hour, and minute — even if such a combination is invalid in the user's local time zone").
There is no way to recover which timezone the browser was in when the value was entered, unless the page
separately captures it (e.g. via JS `Intl.DateTimeFormat().resolvedOptions().timeZone`).

For a Django project with `USE_TZ = True` (Django's own recommendation is to store everything in UTC and
only convert for display — [Django docs: Time zones](https://docs.djangoproject.com/en/6.0/topics/i18n/timezones/)), a raw `datetime-local` submission is ambiguous. Realistic
options, with trade-offs (not a recommendation):

1. **Store as naive, interpret in one configured/fixed timezone** (e.g. the site's `TIME_ZONE` setting,
   or an org-level timezone field). Simple, no extra UI. Wrong if the learner is physically in a
   different timezone than the org's configured one — the recorded moment will be off by the offset
   difference, silently.
2. **Drop `datetime` as a single type; ask for `date` and `time` as two separate questions/fields**,
   and treat the pairing as belonging to a timezone decided by policy elsewhere (same ambiguity as
   option 1, but makes the naivety of the value visually obvious to the spec author since there's no
   single field implying "this is a real instant").
3. **Explicitly capture timezone alongside the value** — e.g. a hidden field populated by JS with the
   browser's IANA timezone name, stored alongside the naive datetime, then localized server-side. Removes
   the ambiguity and gives a correct instant in time, at the cost of extra field/JS plumbing and a
   dependency on JS running (progressive-enhancement/no-JS fallback needed) — a bigger change than "just
   add a question type."
4. **Accept the ambiguity as acceptable for the use case** — e.g. if `datetime` questions in form_engine
   are only ever used for things like "when did this happen" self-report answers where sub-timezone
   precision doesn't matter, the naive value stored as-is (interpreted in server `TIME_ZONE`) may be fine
   and the trade-off is a non-issue in practice.

None of these is "correct" in the abstract; the right choice depends on whether form_engine's `datetime`
questions need to represent a precise instant (e.g. cross-timezone auditing) or just a self-reported
label a human will read back. — [MDN: input/datetime-local](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/datetime-local), [Django docs: Time zones](https://docs.djangoproject.com/en/6.0/topics/i18n/timezones/), [Peterbe.com: Django forms and localized datetime inputs](https://www.peterbe.com/plog/django-forms-and-making-datetime-inputs-localized)

## 6. Pre-filling a stored value into the input

To re-render a previously-submitted answer back into the control on page revisit, the `value` attribute
must be exactly in the wire format for that type — browsers do not accept locale-formatted strings here:

- `date` → `value="YYYY-MM-DD"` (e.g. `value="2026-09-12"`)
- `time` → `value="HH:mm"` or `value="HH:mm:ss"` (e.g. `value="14:30"`)
- `datetime-local` → `value="YYYY-MM-DDTHH:mm"` (e.g. `value="2026-09-12T14:30"`; **note the literal `T`
  separator and no timezone suffix** — including one, e.g. a trailing `Z` or `+02:00`, makes the value
  invalid and the browser will treat the field as empty)

If the stored value came from a Python `date`/`time`/`datetime` object, this is exactly `.isoformat()`
for `date` and `time`; for a Python `datetime`, `.isoformat()` produces a `T` separator and (if the
datetime is timezone-aware) an offset suffix that must be **stripped** before use as a `datetime-local`
value, per the point above. — [MDN: input/date](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/date), [MDN: input/time](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/time), [MDN: input/datetime-local](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/datetime-local)

## References

- [caniuse: `<input type="date">`](https://caniuse.com/mdn-html_elements_input_type_date)
- [caniuse: date and time input types overview](https://caniuse.com/input-datetime)
- [MDN: `<input type="date">` value](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/date)
- [MDN: `<input type="time">` value](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/time)
- [MDN: `<input type="datetime-local">` value](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/datetime-local)
- [MDN: `min` attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/min)
- [MDN: `step` attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/step)
- [Chrome for Developers: Quick FAQs on input[type=date] in Google Chrome](https://developer.chrome.com/blog/quick-faqs-on-input-type-date-in-google-chrome)
- [Peter-Paul Koch (quirksmode/Samsung Internet Developers): Making input type=date complicated](https://www.quirksmode.org/blog/archives/2017/02/making_input_ty.html)
- [Apple Developer Forums: iOS/iPadOS date pickers ignore min/max on opening](https://developer.apple.com/forums/thread/743096)
- [Hassell Inclusion: Is input type="date" ready for use in accessible websites?](https://hassellinclusion.com/blog/input-type-date-ready-for-use/)
- [W3C WAI-ARIA APG: Date Picker Dialog Example](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/datepicker-dialog/)
- [GOV.UK Design System: Date input component](https://design-system.service.gov.uk/components/date-input)
- [Technology in government (GDS blog): Why the GOV.UK Design System team changed the input type for numbers](https://technology.blog.gov.uk/2020/02/24/why-the-gov-uk-design-system-team-changed-the-input-type-for-numbers/)
- [NHS digital service manual: Date input](https://service-manual.nhs.uk/design-system/components/date-input)
- [USWDS: Memorable date component](https://designsystem.digital.gov/components/memorable-date/)
- [USWDS: Date picker component](https://designsystem.digital.gov/components/date-picker/)
- [USWDS: Date of birth pattern](https://designsystem.digital.gov/patterns/create-a-user-profile/date-of-birth/)
- [Shopify Polaris: Date picker component](https://polaris.shopify.com/components/date-picker)
- [Django docs: Time zones](https://docs.djangoproject.com/en/6.0/topics/i18n/timezones/)
- [Peterbe.com: Django forms and making datetime inputs localized](https://www.peterbe.com/plog/django-forms-and-making-datetime-inputs-localized)
- [LambdaTest: HTML Date Input — Browser Support, Types, Limitations](https://www.lambdatest.com/web-technologies/input-datetime)

---
status: ok
reason: completed all six research questions with cited web sources; no blockers encountered
