# Research: field-type inventories in comparable products, checked against the idea's list

## What this settles

The idea's list is largely right. The intersection across every product researched is: single-line
text, long text, single-choice, multi-choice, number, date, and file upload — FLS already has five of
those six via `QuestionType`, and date is the one genuine gap that started this idea. Below is a
per-type verdict.

| Idea's call | Verdict | One line |
|---|---|---|
| Add `date` | **Confirmed, but reconsider the widget.** | Universal across every product surveyed, but GOV.UK's own research (below) found a plain HTML5 `<input type="date">` bad enough that GOV.UK Design System ships a fieldset of three plain-text day/month/year inputs instead — worth a decision line in the spec even if FLS chooses the native picker anyway. |
| Add `time` | **Confirmed, with a caveat.** | Universal in consumer form builders (Google Forms, JotForm) but GOV.UK Design System has **no published time-input component at all** — it's an open backlog item ([alphagov/govuk-design-system-backlog#173](https://github.com/alphagov/govuk-design-system-backlog/issues/173)) — because a good accessible time widget is genuinely unsettled. FLS can still ship `<input type="time">`; just don't assume this is the solved half of the date/time pair. |
| Add `datetime` | **Idea's own hesitation is well-founded — lean toward dropping it.** | No product surveyed offers a single "datetime" question type. Google Forms' date question has an "include time" checkbox that is really two answers under one question, not one combined field. FLS already flagged the naive-timezone problem; the product evidence adds a second reason to just ask for a date and a time separately when both are needed. |
| Add `email` | **Confirmed, but note it's authoring sugar in Google Forms.** | JotForm, Typeform, and GOV.UK Forms all ship a first-class Email type with format validation. Google Forms has **no dedicated email type** — it's a Short Answer with a regex Response Validation rule bolted on. FLS's plan (typed field, server-side `EmailValidator`) matches the JotForm/Typeform/GOV.UK approach, which is the majority position. |
| Add `url` | **Confirmed.** | JotForm and GOV.UK Forms's "website URLs" contact-info type both treat this as first-class; cheap, matches `URLValidator`. |
| Add `phone` | **Confirmed, with the idea's caveat independently corroborated.** | JotForm, Typeform, and GOV.UK Forms all ship a Phone type, but none of them do real validation without a country: `django-phonenumber-field` wraps Google's `libphonenumber` and requires a `PHONENUMBER_DEFAULT_REGION` (or a country selector alongside the number) to parse a national number at all. MDN confirms `<input type="tel">` "does not enforce any constraints on the value entered" and exists to trigger a numeric keypad, not to validate. The idea's framing is exactly right — ship the keyboard hint, state plainly that real validation is out of scope. |
| Add `dropdown` | **Confirmed as a type, but the country justification overstates dropdown's usability.** | See §3 below — dropdown is cheap and matches an intersection of Google Forms, JotForm, and Typeform. But GOV.UK Design System explicitly calls `<select>` "a last resort" ([design-system.service.gov.uk/components/select](https://design-system.service.gov.uk/components/select/)), and Baymard's country-selector research says a plain dropdown is still poor at 200 options and recommends a searchable/autocomplete control instead ([baymard.com/blog/drop-down-usability](https://baymard.com/blog/drop-down-usability), [baymard.com/labs/country-selector](https://baymard.com/labs/country-selector)). Dropdown beats forty radio buttons; it does not make country selection "usable" by the standard the accessibility literature holds it to. Reword the justification, don't drop the type. |
| Leave out `yes_no` | **Confirmed, and GOV.UK gives a positive reason to actively avoid it.** | See §4. Every product that ships a visual Yes/No shortcut (Typeform) implements it as two options on a choice control, not a different storage shape. GOV.UK Design System's guidance goes further: it tells authors to avoid generic "Yes"/"No" labels in favour of descriptive option text (e.g. "Yes, I spend time living at two homes") precisely because bare yes/no is often the wrong question design. A first-class `yes_no` type would encourage the anti-pattern GOV.UK warns against. |
| Leave out `rating`/`scale` | **Confirmed for single-item scales; flag that grid/Likert-matrix is the one real gap, and it's correctly out of scope.** | See §4. Qualtrics and Typeform's NPS/star-rating widgets are presentation sugar over a numbered choice list, exactly matching FLS's existing `CATEGORY_VALUE_SUM` `FormStrategy`. The genuinely different structure is the **matrix/grid** (Google Forms "Multiple Choice Grid"/"Checkbox Grid", Qualtrics Matrix Table) — one scale applied to several sub-items in one question, which needs a different data shape (question × row × selected column) that `FormQuestion`/`QuestionOption` doesn't have today. The idea doesn't mention grids; it should note the omission is deliberate, not overlooked. |
| Leave out multi-file upload | **Confirmed.** | Every product treats multi-file as a variant of file upload, not a new question type; FLS's blocker (`QuestionAnswerFile` as `OneToOneField`) is a storage constraint, not a missing concept. |
| Leave out `address`, `country`, `signature` | **Confirmed — see §6 for why each is a genuinely different cost, not just "more work."** | |

---

## Comparison table: products × field types

Rows are the union of types found; `-` = not offered as a first-class type, `sugar` = achievable but
implemented as a variant/configuration of a simpler type, not separate storage/validation.

| Type | Google Forms | Typeform | JotForm | GOV.UK Forms product | Moodle quiz | Open edX | Django `forms` (floor) | FLS today |
|---|---|---|---|---|---|---|---|---|
| Short text | ✓ (Short Answer) | ✓ | ✓ | ✓ | ✓ (Short Answer, graded) | ✓ (text input) | `CharField` | `short_text` |
| Long text | ✓ (Paragraph) | ✓ | ✓ | ✓ | ✓ (Essay, manual grade) | - | `CharField(widget=Textarea)` | `long_text` |
| Single choice | ✓ (Multiple Choice) | ✓ | ✓ | ✓ (Radios) | ✓ (Multiple Choice) | ✓ | `ChoiceField` | `multiple_choice` |
| Multi choice | ✓ (Checkboxes) | ✓ | ✓ | ✓ (Checkboxes) | ✓ (Multiple Choice, multi-answer) | ✓ | `MultipleChoiceField` | `checkboxes` |
| Dropdown/select | ✓ | ✓ | ✓ | sugar (discouraged, "last resort") | - | - | `ChoiceField(widget=Select)` | proposed |
| Number | sugar (validation rule) | ✓ | ✓ | ✓ | ✓ (Numerical, with tolerance) | ✓ | `IntegerField`/`DecimalField` | `number` |
| Date | ✓ | ✓ | ✓ (Date Picker) | ✓ (Date input, 3-field) | - | - | `DateField` | proposed |
| Time | ✓ | sugar (Scheduler is booking, not a bare time field) | ✓ | not published (backlog) | - | - | `TimeField` | proposed |
| Datetime (single type) | sugar ("include time" on Date) | - | sugar (Date Picker + time) | - | - | - | `SplitDateTimeField` (already split) | proposed, idea leans against |
| Email | sugar (regex validation) | ✓ | ✓ | ✓ | - | - | `EmailField` | proposed |
| URL | sugar | ✓ | ✓ (via widgets) | sugar | - | - | `URLField` | proposed |
| Phone | - | ✓ | ✓ | ✓ | - | - | none built-in (needs `django-phonenumber-field`) | proposed |
| File upload | ✓ (single) | - | ✓ | ✓ | - | - | `FileField` | `file_upload` |
| Yes/No | sugar (2-option MC) | ✓ (styled MC) | sugar | sugar (2-option Radios, discouraged as bare labels) | ✓ (True/False, fixed penalty=1) | - | `NullBooleanField`/`BooleanField` | not proposed |
| Rating/scale (single item) | ✓ (Linear Scale) | ✓ (Opinion Scale, Rating, NPS) | ✓ (Scale Rating) | - | - | - | - | not proposed |
| Matrix/grid | ✓ (MC Grid, Checkbox Grid) | ✓ (Matrix) | via Configurable List widget | - | - | - | - | not proposed, not mentioned by idea |
| Address | - | ✓ (contact-info group) | ✓ | ✓ (UK/international) | - | - | - | not proposed |
| Signature | - | ✓ | ✓ | - | - | - | - | not proposed |
| Ranking/ordering | - | ✓ | via Orderable List widget | - | ✓ (Ordering) | - | - | not proposed |

Sources for the table: Google Forms ([support.google.com/docs/answer/7322334](https://support.google.com/docs/answer/7322334), [jotform.com/google-forms/google-forms-question-types](https://www.jotform.com/google-forms/google-forms-question-types/)); Typeform ([help.typeform.com/hc/en-us/articles/360051789692](https://help.typeform.com/hc/en-us/articles/360051789692-Question-types), [forms.app/en/blog/typeform-question-types](https://forms.app/en/blog/typeform-question-types)); JotForm ([jotform.com/features/form-fields](https://www.jotform.com/features/form-fields/), [jotform.com/help/guide-jotform-widgets](https://www.jotform.com/help/guide-jotform-widgets/)); GOV.UK Forms product ([forms.service.gov.uk/about/features](https://www.forms.service.gov.uk/about/features)) and GOV.UK Design System components ([design-system.service.gov.uk/components](https://design-system.service.gov.uk/components/)); Moodle ([docs.moodle.org/502/en/Question_types](https://docs.moodle.org/502/en/Question_types)); Open edX ([docs.openedx.org/en/latest/educators/references/course_development/exercise_tools/guide_problem_types.html](https://docs.openedx.org/en/latest/educators/references/course_development/exercise_tools/guide_problem_types.html)); Django form fields ([docs.djangoproject.com/en/6.0/ref/forms/fields](https://docs.djangoproject.com/en/6.0/ref/forms/fields/)).

---

## 1–2. Field-type inventories and the intersection

**Google Forms** (11–12 named types): Short Answer, Paragraph, Multiple Choice, Checkboxes, Dropdown,
Date, Time, Linear Scale, Multiple Choice Grid, Checkbox Grid, File Upload. Email/URL/phone are not
types — they're a Short Answer plus a "Response Validation" regex rule. This is the cleanest example
of "authoring sugar over a simpler storage shape": Google chose not to multiply question types and
instead layered validation onto one text type.
[support.google.com/docs/answer/7322334](https://support.google.com/docs/answer/7322334)

**Typeform**: groups its picker into "Contact info" (Email, Phone Number, Website/URL, Address), "Choice"
(Multiple Choice, Dropdown, Picture Choice, Yes/No, Checkboxes, Legal), "Rating and ranking" (Opinion
Scale, Rating, NPS, Ranking, Matrix/Likert), and standalone Long Text, Signature, Scheduler.
[help.typeform.com/hc/en-us/articles/360051789692](https://help.typeform.com/hc/en-us/articles/360051789692-Question-types),
[forms.app/en/blog/typeform-question-types](https://forms.app/en/blog/typeform-question-types)

**JotForm**: Short Text, Long Text, Multiple Choice, Checkboxes, Number, Name, Email, Phone Number,
Address, Date Picker (with an optional attached time field), Signature, Scale Rating, Dropdown, File
Upload, plus a large widget library (Configurable List, Field Multiplier, Country Picker, Orderable
List) for anything more composite.
[jotform.com/features/form-fields](https://www.jotform.com/features/form-fields/),
[jotform.com/help/guide-jotform-widgets](https://www.jotform.com/help/guide-jotform-widgets/)

**GOV.UK** — two things worth separating. The **GOV.UK Forms product** (the hosted form builder civil
servants use) lists its available question types plainly: name, phone number, email address, UK or
international address, National Insurance number, date, number, file, single/multi-choice, short or
long text. [forms.service.gov.uk/about/features](https://www.forms.service.gov.uk/about/features). The
**GOV.UK Design System** (the underlying component library) is more conservative: Text input, Textarea,
Radios, Checkboxes, Select, Date input, File upload — and explicitly declines to ship several
"sugar" patterns (Yes/No, ratings) as separate components, treating them as configurations of Radios.
[design-system.service.gov.uk/components](https://design-system.service.gov.uk/components/)

**Moodle quiz** and **Open edX** skew toward gradable types, as expected for LMS assessment engines:
Moodle has Multiple Choice, True/False, Short Answer, Numerical (with tolerance), Matching, Essay
(manually graded), Ordering, Cloze/embedded-answer, and several randomised/calculated variants aimed
at exam-style auto-marking. [docs.moodle.org/502/en/Question_types](https://docs.moodle.org/502/en/Question_types).
Open edX's "Common Problem Types" are multiple choice and text/numeric input; its "Advanced" list adds
math-expression input, drag-and-drop-on-image, image-mapped input, and open-response (essay)
assessment — none of it date/time/contact-info, because Open edX problems are graded exercises, not
intake forms. [docs.openedx.org/.../guide_problem_types.html](https://docs.openedx.org/en/latest/educators/references/course_development/exercise_tools/guide_problem_types.html).
Neither LMS offers date, email, phone, or URL as question types at all — that's a form-builder concern,
not a quiz-engine one, which matches FLS's own split between `course_applications` (form) and the quiz
runner (assessment).

**Django's own `forms` module** is a useful floor: `CharField`, `EmailField`, `URLField`, `DateField`,
`TimeField`, `IntegerField`/`DecimalField`, `ChoiceField`/`MultipleChoiceField`, `FileField`,
`BooleanField`/`NullBooleanField`. Everything the idea proposes to add already exists as a first-class
Django form field with a validator; nothing proposed requires inventing new validation logic from
scratch. [docs.djangoproject.com/en/6.0/ref/forms/fields](https://docs.djangoproject.com/en/6.0/ref/forms/fields/)

**Intersection.** Short text, long text, single choice, multi choice, number, date, and file upload
appear in essentially every product surveyed except the two LMS quiz engines (which skip date/contact
types because they're not intake forms) — FLS already has six of these seven; **date** is the one gap,
confirming the original ask. Dropdown, email, phone, and URL appear in most consumer/gov form builders
but in neither quiz engine, consistent with FLS treating them as `course_applications`-oriented
additions rather than quiz-oriented ones. No product outside the LMS-quiz pair treats date/time
question types as anything other than plain intake fields — none of them attach scoring to a date, which
lines up with the idea's decision 4 (quiz scoring stays out of scope for the new types).

---

## 3. Dropdown vs radio buttons: what the published guidance actually says

- **Nielsen Norman Group**, "Listboxes vs. Dropdown Lists": use radio buttons/checkboxes for **5 or
  fewer** options; switch to a dropdown or listbox at **5 or more**. Between 5 and 15, "use a dropdown
  if screen space is limited, use a listbox if it is not." Above roughly 15, prefer a listbox with most
  options visible over a dropdown that forces scrolling.
  [nngroup.com/articles/listbox-dropdown](https://www.nngroup.com/articles/listbox-dropdown/)
- **USWDS**: "Use the select component only when a user needs to choose from about **seven to 15**
  possible options and you have limited space to display the options." Also warns against
  auto-submitting on selection change because it disrupts screen readers.
  [designsystem.digital.gov/components/select](https://designsystem.digital.gov/components/select/)
- **GOV.UK Design System** is the outlier and directly relevant to the idea's country-question example:
  it recommends `<select>` be used "only as a last resort in public-facing services because research
  shows that some users find selects very difficult to use," and to try reducing the option count with
  better question design (i.e., prefer Radios) before reaching for Select. Documented failure modes:
  users can't close the dropdown, try to type into it, confuse focus with selection, can't pinch-zoom
  it on mobile, and don't realise it scrolls.
  [design-system.service.gov.uk/components/select](https://design-system.service.gov.uk/components/select/)
- **Baymard Institute**, on country selectors specifically (the idea's own example): a plain dropdown
  with 200+ uncategorised options is "bewildering," has unclear sorting, scrolling problems, no mobile
  context, and breaks tab-flow. Baymard's recommended fix isn't "use a dropdown instead of radios" —
  it's a **searchable/autocomplete field**, built as a progressive enhancement over a plain `<select>`
  so the fallback stays accessible.
  [baymard.com/blog/drop-down-usability](https://baymard.com/blog/drop-down-usability),
  [baymard.com/labs/country-selector](https://baymard.com/labs/country-selector)

**Verdict on the idea's claim.** "The difference between a usable country question and forty radio
buttons" is directionally right (a dropdown is unambiguously better than forty radios — NNG's own
5-option threshold and USWDS's 7–15 guidance both point to Select over Radios once an author gets
anywhere near forty options) but overstates the destination: none of the accessibility literature calls
a plain `<select>` with 195+ countries "usable," and GOV.UK's own published position is to avoid
`<select>` even for moderate lists. FLS should still add `dropdown` — it is cheap, matches
`QuestionOption`/`selected_options` exactly as the idea describes, and is strictly better than a wall of
radios for anything past ~7–10 options — but the spec's justification should say "better than radios
at this option count" rather than implying it solves the country-list case outright. A searchable
country field, if ever wanted, is future work.

---

## 4. `yes_no` and rating/scale: sugar or first-class?

**`yes_no`.** Typeform ships a styled Yes/No control, but it renders as two large buttons over what is
still a single-select choice question — no different storage than `multiple_choice` with two options.
Moodle's True/False is closer to a real distinct type because it carries fixed grading semantics (a
penalty factor that is "always 1," i.e., no partial credit) — but that is a Moodle *quiz-scoring* detail,
not a *forms* concern, and FLS's `is_quiz_answer_correct` already treats any two-option `multiple_choice`
the same way. GOV.UK Design System goes further than "it's sugar" — it actively steers authors away from
bare "Yes"/"No" labels toward descriptive option text tied to the actual question (its example:
replacing Yes/No with "Yes, I spend time living at two homes" / "Yes, I'm a student with home and
term-time addresses"). A first-class `yes_no` type would bake in the exact anti-pattern GOV.UK's own
service manual warns against; leaving it as "author two options on a `multiple_choice`" is not just
cheaper, it's the better authoring practice. This corroborates, and strengthens, the idea's decision to
leave it out.
[docs.moodle.org/502/en/True/False_question_type](https://docs.moodle.org/502/en/True/False_question_type)

**Rating/scale.** Google Forms' Linear Scale, Typeform's Opinion Scale/Rating/NPS, and JotForm's Scale
Rating are all a numbered range (typically 1–5, 1–10, or 0–10) with optional end labels — structurally
identical to `multiple_choice` with N generated numeric options, which is exactly what FLS's
`CATEGORY_VALUE_SUM` `FormStrategy` already sums over. Star widgets and NPS colour-coding
(promoter/passive/detractor) are presentation, not a new answer shape. The one place a real structural
gap exists is the **matrix/Likert grid** — Google Forms' Multiple Choice Grid/Checkbox Grid and
Qualtrics' Matrix Table apply one shared scale across several sub-items in a single question, which is a
question × row × column shape `FormQuestion`/`QuestionOption` doesn't represent today. The idea doesn't
mention grids at all; worth stating in the spec that this omission is deliberate (matrix questions are a
different data model, not a `QuestionType` addition) rather than something research missed.
[qualtrics.com/support/.../question-types-overview](https://www.qualtrics.com/support/survey-platform/survey-module/editing-questions/question-types-guide/question-types-overview/)

---

## 5. `phone`, `email`, `url`: how much validation do real products apply?

- **Email**: JotForm and GOV.UK Forms validate format server-side; Google Forms achieves the same result
  via a bolt-on regex rule on a plain text answer rather than a dedicated type. Either way the actual
  check is a syntax regex — none of them verify deliverability. Django's `EmailValidator`/`EmailField`
  does the same syntax-only check, so the idea's plan (typed field, `EmailValidator` server-side) matches
  the ceiling every comparable product actually reaches.
- **URL**: same story — `URLValidator` is a syntax/scheme check, matching JotForm's dedicated field and
  Typeform's "website URL" contact-info type.
- **Phone**: this is where the idea's caution is best supported by evidence. `django-phonenumber-field`
  wraps `python-phonenumbers` (a port of Google's `libphonenumber`) and needs either a
  `PHONENUMBER_DEFAULT_REGION` setting or an explicit country code to parse a *national* number format
  at all — there is no country-agnostic phone regex that actually validates. MDN's own reference for
  `<input type="tel">` states it plainly: the type "does not enforce any constraints on the value
  entered by a user (this means it may include letters, etc.)"; its only real effect is triggering a
  numeric keypad on touch devices. FLS should ship `phone` as a bare typed field with that keyboard hint
  and say so explicitly in the spec — real validation is a `django-phonenumber-field` + country-selector
  feature that is legitimately out of scope here.
  [django-phonenumber-field.readthedocs.io](https://django-phonenumber-field.readthedocs.io/en/latest/phonenumbers.html),
  [developer.mozilla.org/.../input/tel](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/tel)

---

## 6. Types FLS should consciously refuse, and the actual cost of each

- **Address.** GOV.UK Forms and JotForm both ship it, but as a composite of several sub-fields (line 1,
  line 2, town/city, postcode, and — for GOV.UK's "international" variant — a country). That's several
  `QuestionAnswer` rows or a structured value per question, not a string in `text_answer`. Real cost:
  composite storage, not validation.
- **Country.** Needs a maintained reference list (ISO 3166, ~195 entries, translated) — the natural
  Django answer is a package like `django-countries`, not a hand-authored `QuestionOption` list per
  form. Real cost: a reference-data dependency the course author shouldn't have to hand-roll in YAML
  every time, plus (per Baymard, above) a search/autocomplete UI if it's to be usable at all.
- **Signature.** JotForm and Typeform both support it because e-signatures carry legal weight in their
  target use cases (contracts, consent forms); implementing it means a drawing/typed-signature capture
  widget and image or vector storage, not a string. Real cost: new storage type (image) plus UI capture
  code, unrelated to anything `text_answer` does today.
- **Currency.** Not offered as a distinct type by any product surveyed (usually just Number with a
  formatting hint), but worth naming: real cost would be locale-aware formatting and rounding rules,
  which is more precision than any surveyed product actually promises.
- **Multi-file upload.** Every product treats it as file upload with a "multiple" flag, not a new
  concept — but in FLS specifically, `QuestionAnswerFile` is a `OneToOneField` off the answer
  (`models.py:660`), so multi-file needs a schema change (to a `ForeignKey` or M2M), independent of
  anything about question types.
- **Matrix/grid (Likert-style).** Google Forms and Qualtrics both ship this. Real cost: a question ×
  row × column data shape that `FormQuestion`/`QuestionOption`/`QuestionAnswer` don't represent — this
  is the one type from the survey the idea doesn't explicitly call out as refused, and it should be,
  for the reason given in §4.

---

## Reference URLs

- Google Forms question types: [support.google.com/docs/answer/7322334](https://support.google.com/docs/answer/7322334), [jotform.com/google-forms/google-forms-question-types](https://www.jotform.com/google-forms/google-forms-question-types/)
- Google Forms email validation is a regex rule, not a type: [usebouncer.com/google-form-email-validation](https://www.usebouncer.com/google-form-email-validation/)
- Typeform question types: [help.typeform.com/hc/en-us/articles/360051789692](https://help.typeform.com/hc/en-us/articles/360051789692-Question-types), [forms.app/en/blog/typeform-question-types](https://forms.app/en/blog/typeform-question-types)
- JotForm fields and widgets: [jotform.com/features/form-fields](https://www.jotform.com/features/form-fields/), [jotform.com/help/guide-jotform-widgets](https://www.jotform.com/help/guide-jotform-widgets/), [jotform.com/help/46-quick-overview-of-form-fields](https://www.jotform.com/help/46-quick-overview-of-form-fields/)
- GOV.UK Forms product features: [forms.service.gov.uk/about/features](https://www.forms.service.gov.uk/about/features)
- GOV.UK Design System components: [design-system.service.gov.uk/components](https://design-system.service.gov.uk/components/)
- GOV.UK Design System, Select component ("last resort"): [design-system.service.gov.uk/components/select](https://design-system.service.gov.uk/components/select/)
- GOV.UK Design System, Date input (3-field, day/month names accepted): [design-system.service.gov.uk/components/date-input](https://design-system.service.gov.uk/components/date-input)
- GOV.UK time input still unpublished/backlog: [github.com/alphagov/govuk-design-system-backlog/issues/173](https://github.com/alphagov/govuk-design-system-backlog/issues/173)
- Moodle question types: [docs.moodle.org/502/en/Question_types](https://docs.moodle.org/502/en/Question_types), True/False: [docs.moodle.org/502/en/True/False_question_type](https://docs.moodle.org/502/en/True/False_question_type)
- Open edX problem types: [docs.openedx.org/.../guide_problem_types.html](https://docs.openedx.org/en/latest/educators/references/course_development/exercise_tools/guide_problem_types.html)
- Qualtrics question types (Matrix, NPS, Slider): [qualtrics.com/support/.../question-types-overview](https://www.qualtrics.com/support/survey-platform/survey-module/editing-questions/question-types-guide/question-types-overview/)
- Django form fields (the floor): [docs.djangoproject.com/en/6.0/ref/forms/fields](https://docs.djangoproject.com/en/6.0/ref/forms/fields/)
- Nielsen Norman Group, Listboxes vs. Dropdown Lists (5/15 option thresholds): [nngroup.com/articles/listbox-dropdown](https://www.nngroup.com/articles/listbox-dropdown/)
- Nielsen Norman Group, Checkboxes vs. Radio Buttons: [nngroup.com/articles/checkboxes-vs-radio-buttons](https://www.nngroup.com/articles/checkboxes-vs-radio-buttons/)
- Nielsen Norman Group, Date-Input Form Fields: [nngroup.com/articles/date-input](https://www.nngroup.com/articles/date-input/)
- USWDS Select component (7–15 option guidance): [designsystem.digital.gov/components/select](https://designsystem.digital.gov/components/select/)
- Baymard Institute, drop-down usability: [baymard.com/blog/drop-down-usability](https://baymard.com/blog/drop-down-usability)
- Baymard Institute, redesigning the country selector: [baymard.com/labs/country-selector](https://baymard.com/labs/country-selector)
- MDN, `<input type="tel">` (not validated, keypad hint only): [developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/tel](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/tel)
- django-phonenumber-field / libphonenumber, needs a default region to parse: [django-phonenumber-field.readthedocs.io/en/latest/phonenumbers.html](https://django-phonenumber-field.readthedocs.io/en/latest/phonenumbers.html)

---

status: ok
reason: Researched field-type inventories across Google Forms, Typeform, JotForm, GOV.UK Forms/Design System, Moodle, Open edX, and Django's own form fields; validated the idea's add/leave-out list against them and against published NN/g, GOV.UK, USWDS, and Baymard usability guidance on dropdown vs radios, yes_no, and rating/scale. All citations are live web sources gathered this session.
