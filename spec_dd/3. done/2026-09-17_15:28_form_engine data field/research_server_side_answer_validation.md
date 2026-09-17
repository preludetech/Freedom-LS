# Research: server-side answer validation — where it lives, where it surfaces

## What this settles

**The idea's claim that "the form_engine quiz runner has no equivalent path at all" is wrong.**
`freedom_ls/learner_interface/views.py` (the runner's `form_fill_page` view, POST branch around
line 1377) computes `unanswered_required_on_page`, calls `form_progress.save_answers(...)`
regardless, and re-renders `learner_interface/course_form_page.html` with
`status=422 if required_answers_error else 200` — the identical shape to
`course_applications/views.py:application_form_page` (line 201–234). Both runners already share
`unanswered_required_on_page` / `unanswered_required_message` / `save_answers` from
`form_engine/paging.py` and `form_engine/models.py`. There is exactly one existing validation path
in `form_engine`, used identically by both callers. The spec does not need to invent a second one
for the runner; it needs to **extend the one that exists**.

What actually is true, and does need solving: `required_answers_error` (both views) is a single
form-level string rendered once as a callout above the form
(`course_applications/templates/course_applications/form_page.html:32-34`,
`learner_interface/templates/learner_interface/course_form_page.html:279-285`). There is no
per-question error slot anywhere — `form_engine/templates/form_engine/question.html` has no error
element at all except the one hard-coded, hidden `<p data-checkbox-required-message>` for
`checkboxes` (question.html:50-56), which Alpine (`examRunnerForm`) reveals client-side and which
never appears under the application shell (nothing there reveals it — confirmed by reading the
comment on question.html:44-49). A typed field failing content validation (a `date` question
holding `banana`) needs a **new** per-question error mechanism; the required-field check needs no
new mechanism, only a new failure mode to feed into the existing one.

### The concrete options for where validation lives

1. **View-level, following the existing `unanswered_required_on_page` pattern exactly.** A new
   function alongside it — e.g. `invalid_answers_on_page(questions, post_data)` — parses each
   typed free-text answer with the matching Django utility (`parse_date`, `EmailValidator`, etc.),
   returns the questions that fail, and both view POST branches feed the result into the same
   422-re-render they already do. This is what the prior research for this app
   (`spec_dd/3. done/2026-09-10_09:45_simple-application-forms/research_question_types_and_validation.md`,
   §4) recommended for exactly this reason: `submitted_text_answer`/`has_submitted_answer` are read
   by every free-text-aware module through `FREE_TEXT_QUESTION_TYPES`, and the view is the only
   layer holding `post_data`, `form_progress`, and the render call together. **Trade-off:** stays
   consistent with 100% of existing form_engine conventions; costs one small new function in
   `submissions.py` or `paging.py` and a second sweep of `questions` in each of the two view POST
   branches (one for presence, one for content) — or a merge of both sweeps into one loop that
   returns two lists. Per-question errors still need a place to render (see below); this option
   does not solve that on its own — it only decides where the checking happens.

2. **A real `django.forms.Form` built per page, one field per `FormQuestion`.** Each row gets a
   dynamically-added `forms.DateField`/`forms.EmailField`/etc. via `fields[f"question_{q.id}"] = ...`,
   and Django's own `form.is_valid()` / `form.errors[field_name]` supplies per-field errors for
   free. **Trade-off, stated honestly:** FLS currently hand-rolls every widget as a template partial
   under `form_engine/templates/form_engine/inputs/` (`short_text.html`, `number.html`, etc.) and
   `save_answers` writes `post_data` straight to `QuestionAnswer.text_answer`/`selected_options`
   with no `Form` in between. Adopting a real `Form` here means either (a) throwing away the
   existing template partials in favour of Django's auto-rendered field HTML — which would have to
   be re-skinned with FLS's Tailwind classes and `sr-only` labels, i.e. rebuilding what the
   partials already do — or (b) keeping the partials as the widgets and only using the `Form`
   for validation, at which point the `Form` is inserted purely as a bag of per-field validators
   and the same field-construction machinery has to mirror `question.type` anyway. Given the
   partials already exist, are already correctly wired for `existing_answers`/`read_only`/HTMX, and
   `save_answers` already writes directly, a per-page `Form` buys per-field error dict for free but
   costs a second, parallel definition of "what type is this question" (once in `QuestionType`,
   once in the dynamically-built `Form` field map) and a rewrite of `save_answers` to read from
   `form.cleaned_data` instead of `post_data`. It is a legitimate option, not a wrong one, but it is
   not the cheaper one, and it does not remove the need for a per-question error *template* slot —
   Django's `form.errors` still needs somewhere in `question.html` to render.

3. **Field-level validation errors rendered via HTMX partial per question**, mirroring the file
   upload endpoints. `freedom_ls/form_engine/views.py`
   (`partial_question_file_upload`/`partial_question_file_remove`) is the one place in `form_engine`
   that already does exactly this: it validates (`validate_and_sanitise`), catches
   `ValidationError`, and re-renders **just that question's widget partial**
   (`form_engine/inputs/file_upload.html`) with `error=err.messages[0]` and `status=422`
   (`views.py:93-98`), swapped in by HTMX rather than a full-page POST. This is the closest existing
   precedent for a *per-question* error and confirms the pattern the project already uses when it
   wants one: **the error string is a template variable the widget partial itself renders**, not a
   form-level callout. Applying this to typed free-text answers would mean giving each `inputs/*.html`
   partial (not just `file_upload.html`) an `error` slot, and either (a) making every question POST
   an individual HTMX request per field (a much bigger change to how the page currently submits —
   today the whole page is one native `<form>` POST, not per-field `hx-post`), or (b) keeping the
   whole-page POST and threading a `dict[question_id, error]` through the full-page 422 re-render so
   `question.html` can look up its own question's error when rendering — reusing the *shape* of the
   file-upload precedent (per-question error string) without adopting HTMX per-field submission.
   (b) is the one that fits the existing full-page-POST architecture; (a) would be the far larger,
   probably unjustified, change.

**Recommended shape for the later spec to decide between, stated plainly**: keep the existing
whole-page POST and 422 re-render (option 1's checking, done in the view or `submissions.py`),
but stop passing a single `required_answers_error` string and instead pass (or extend it into) a
`dict[question_id, str]` of per-question errors that `question.html` reads to render its own error
element next to its own input, keyed by `id="question_{{ question.id }}"` — i.e., adopt the
*per-question error slot* the file-upload precedent already establishes, without adopting a
`django.forms.Form` or per-field HTMX submission. That is a decision for the spec, not this
research — but it is the option that costs the least against what already exists and is internally
consistent with the one per-question error precedent (`form_engine/views.py`) the codebase already has.

### The trap the idea's decision 3 (min/max) walks straight into

**Re-showing a rejected date value in `<input type="date" value="...">` does not work — the browser
silently blanks it.** Confirmed via MDN and cross-browser bug reports: `<input type="date">` has a
"value sanitization algorithm" that accepts only a value already in canonical `yyyy-mm-dd` form; any
string that doesn't parse as a valid date is treated as if the `value` attribute were absent, so the
field renders empty. WebKit clears an in-progress invalid typed value on blur/submit; Opera silently
submits an empty sanitised value while leaving the visible typed characters; the invalid string
is never round-tripped back to the value attribute space at all
([MDN — `<input type="date">`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/date);
[WHATWG thread on incomplete user input in date-like input types](https://lists.whatwg.org/pipermail/whatwg-whatwg.org/2012-September/037280.html)).
This means FLS's existing "always save what was submitted, so a rejected page doesn't lose work"
principle (the docstring on `application_form_page`, `course_applications/views.py:180-182`) has a
real conflict for date/time/datetime fields specifically: if the server stores the raw rejected
string `banana` in `text_answer` (because the whole-page save-what-you-can flow runs unconditionally
today via `save_answers`, before any content check exists) and then re-renders the page with
`value="banana"` on a `<input type="date">`, the browser shows an **empty** box, not the value the
learner typed — the person cannot see what they entered, cannot tell what was wrong with it, and the
callout/error message is the only place the rejected value could be surfaced at all (e.g., "You
entered 'banana', which is not a valid date"). Two honest ways out, for the spec to choose between:
render the rejected raw string back through a plain `<input type="text">`-styled fallback when
content validation fails (giving up the native date picker for that one round-trip), or drop the
rejected string from the value attribute and only recite it in the error text next to the field.
Silently discarding the invalid string without saying what it was is also an option but breaks the
existing "never lose the learner's own words" spirit found elsewhere in this app; naming this
trade-off explicitly is the deliverable of this section.

**Time and datetime-local inputs have the same value-sanitization behavior** (also documented on the
adjoining MDN pages for `input/time` and `input/datetime-local`, part of the same "if the value
doesn't match the expected microsyntax, the control is empty" rule the HTML spec applies uniformly
across all these input types) — nothing about `date` specifically is worse than `time` or
`datetime-local` here; the trap applies to all three new types the idea proposes.

---

## The existing validation path, read closely

`freedom_ls/form_engine/submissions.py`:

- `submitted_option_ids` (line 13) — choice answers, filters blank values from `getlist`.
- `submitted_text_answer` (line 18) — `.strip()`, nothing else. This is the entire content
  sanitisation `form_engine` performs today, for every free-text type.
- `has_submitted_answer` (line 23) — branches on `FREE_TEXT_QUESTION_TYPES` to decide "non-blank
  text" vs. "non-empty option list"; a `FILE_UPLOAD` question is always `False` here because its
  answer arrives on a separate request (`form_engine/views.py`), never the page POST.

`freedom_ls/form_engine/paging.py`:

- `unanswered_required_on_page` (line 97) — the per-page required-field check both views call,
  measuring `has_submitted_answer` against `post_data`, with the file-upload exception measured
  against the stored row instead (`is_answered`, line 22).
- `unanswered_required_in_form` (line 120) — the whole-form sweep `application_check_answers` runs
  at final submission, catching a required question on a page never visited.
- `unanswered_required_message` (line 135) — builds the single string both views drop into
  `required_answers_error`; e.g. `"Questions 2, 5 and 7 need answers before you can continue."` —
  this function has no concept of *which* question failed *what*, only "is unanswered."

`freedom_ls/form_engine/models.py`:

- `FormQuestion` (line 133) — `type`, `required`; no bounds fields, no validator hook.
- `QuestionAnswer` (line 602) — `selected_options` M2M, `text_answer` `TextField(blank=True,
  default="")`. No `clean()`, no model-level constraint on content.
- `FormProgress.save_answers` (line 310) — for each question, if
  `not has_submitted_answer(question, post_data)` it **deletes** any existing answer row; otherwise
  it `get_or_create`s the row and writes `submitted_text_answer(...)` or
  `submitted_option_ids(...)` unconditionally. There is no branch here that could reject a value —
  every path that reaches this function today always ends in a write. Any content validation added
  ahead of this call has to stop `save_answers` being invoked for the rejected question specifically
  (or accept that the rejected string gets written anyway, per the trap above).
- `FormProgress.existing_answers_dict` (line 294) — reads the whole answer set once and filters in
  Python; this is what feeds `value="..."` back into every widget partial on re-render, so it is
  also the mechanism that would carry a rejected value back to the browser (and hit the date-input
  trap) if nothing intervenes.

`freedom_ls/course_applications/views.py::application_form_page` (line 174–238) and
`freedom_ls/learner_interface/views.py` (the runner's per-page view, POST branch at line
1366–1398): **structurally identical.** Both: compute unanswered-required against `post_data`, call
`save_answers` unconditionally (so a rejected submission never loses good answers — the explicit
intent stated in the docstring at `course_applications/views.py:178-182`), then render the same page
template with `status=422 if required_answers_error else 200`. Neither has any per-question error
concept; both pass exactly one string.

`freedom_ls/course_applications/views.py::application_check_answers` (line 242) does the same shape
against `unanswered_required_in_form`, for the final whole-form submit.

Templates: `course_applications/templates/course_applications/form_page.html:32-34` and
`learner_interface/templates/learner_interface/course_form_page.html:279-285` both render
`required_answers_error` as a single `<c-callout level="error">` above the whole form (the runner
also wraps it in `role="alert"` and a `data-testid`). `check_your_answers.html:18-20` does the same
for the whole-form check. None of the three offers a per-field slot.

`form_engine/templates/form_engine/question.html` (57 lines total) has **no error element** for any
question type except the hidden, Alpine-revealed `<p data-checkbox-required-message>` at lines
50–56, which the comment there explicitly says "outside the runner nothing reveals it" — i.e. it is
already a special case that only exists because a checkbox group cannot be natively `required`
validated by the browser at all. The `inputs/short_text.html` and `inputs/number.html` partials
(read in full) are plain, unstyled-for-error `<input>` tags with `{% if question.required %}required{%
endif %}` and a `value="{{ answer.text_answer }}"` echo — no `aria-invalid`, no `aria-describedby`,
no error slot to wire up.

`freedom_ls/form_engine/views.py` — the file-upload partial endpoints
(`partial_question_file_upload`, lines 78–111; `partial_question_file_remove`, lines 114–133) are
the one place in `form_engine` doing real per-question, per-HTMX-request content validation today:
`validate_and_sanitise(uploaded)` raises `django.core.exceptions.ValidationError`, caught and turned
into `_render_file_widget(..., error=err.messages[0], status=422)` (lines 93–98), which re-renders
only `FILE_WIDGET_TEMPLATE` ("form_engine/inputs/file_upload.html") — not the whole page — carrying
an `error` context variable the partial presumably renders next to the widget. This is a genuinely
different transport (its own `hx-post` per file question, not the whole-page native POST every other
question type uses) but it is proof the codebase already has, and already uses, the *concept* of "an
error string that belongs to one question's widget partial, not the whole page."

## House convention on status codes

`claude_plugins/django-stack/skills/htmx/SKILL.md` states plainly: "**422** for validation errors on
HTMX requests" (line 66), alongside "200 for successful responses." Both existing form_engine
validation paths already follow this for the whole-page native-submit case (not `hx-post` — a plain
form POST — but still 422 on rejection), and the file-upload endpoints follow it for the genuinely
HTMX case. Whatever is added for typed-field content validation should return 422 the same way,
whichever of the shapes above the spec picks.

---

## External research

### 1. Django's own validation tools, and their gotchas for a free-standing string

- **`django.core.validators.EmailValidator`** — used via `django.forms.EmailField` normally, but
  callable directly: `EmailValidator()(value)` raises `django.core.exceptions.ValidationError` or
  passes silently. Gotcha: values over 320 characters are always rejected regardless of shape;
  the default `allowlist` is `['localhost']`, meaning any other single-label domain (no dot) is
  rejected by default — a plausible trap for an internal test address, not for genuine applicant
  email addresses. ([Django validators reference](https://docs.djangoproject.com/en/6.1/ref/validators/))
- **`django.core.validators.URLValidator`** — same direct-call shape. Gotcha, and the one worth
  spelling out for the idea's `url` type: **`URLValidator` requires a scheme.** `"example.com"`
  typed with no `http://`/`https://` fails validation outright — Django's own `forms.URLField`
  papers over this by *prepending* a default scheme to the cleaned value before validating (an
  `assume_scheme` mechanism), but the bare `URLValidator` class does not do this itself. A learner
  who types `linkedin.com/in/me` into a bare `url` field, validated with a bare `URLValidator`, gets
  rejected for a perfectly reasonable input; the fix is either to prepend `https://` before
  validating (mirroring what `forms.URLField` does) or accept the rejection and word the error
  message to say a scheme is required.
  ([Django Forum: URL validation without schemes](https://forum.djangoproject.com/t/url-validation-without-schemes/15900);
  [Adam Johnson: Django's `URLField.assume_scheme`](https://adamj.eu/tech/2023/12/07/django-fix-urlfield-assume-scheme-warnings/);
  [Django validators reference](https://docs.djangoproject.com/en/6.1/ref/validators/))
- **`django.utils.dateparse.parse_date` / `parse_time` / `parse_datetime`** — the natural fit for
  validating a bare ISO-8601 string outside a `Form`, since they take a string and return either a
  `date`/`time`/`datetime` object or `None`, with no `Form`/`Field` machinery required. **The
  gotcha that matters most for this spec: they do not behave uniformly.** A string that is not
  well-formed at all (`"banana"`) returns `None` — no exception. A string that *is* well-formed but
  not a real date (`"2023-13-45"`, month 13) **raises `ValueError`**, not `None`. Any code calling
  these to validate a submitted answer must catch both cases — a bare `if parse_date(value) is
  None:` check alone will 500 on `"2023-13-45"` instead of treating it as a validation failure.
  They accept ISO 8601 "or some close alternatives"; `parse_datetime` supports a UTC offset,
  `parse_time` does not (returns `None` if one is present).
  ([Django `dateparse` reference](https://docs.djangoproject.com/en/6.0/ref/utils/#module-django.utils.dateparse))
- **`forms.DateField`/`forms.TimeField`** — go through `INPUT_FORMATS`/localized parsing rather than
  `dateparse` directly, accepting multiple formats (ISO plus locale-specific ones) unless
  `DATE_INPUT_FORMATS` is narrowed in settings; heavier than needed if the wire format is always the
  ISO string an `<input type="date">` submits, but the natural choice if the project ever wants to
  accept a typed, non-native-picker date field.
- **`MinValueValidator`/`MaxValueValidator`** — trivial to call directly on a parsed `int`/`date`
  once the string has already been parsed; not useful as strings-in-strings-out validators
  themselves, only after the value is native-typed. These are a natural fit for the idea's `min`/
  `max` decision, applied *after* `parse_date`/`int()` succeeds, not as a substitute for parsing.

**Net for this project:** none of these are designed to be dropped into `submitted_text_answer` as
a single call — every one of them either needs to be instantiated as an object (`EmailValidator()`)
and called for its side effect (raise vs. no raise), or needs its `None`-vs-`raise` duality handled
explicitly (`dateparse`). A thin per-type validate function (`validate_date_answer(text) -> str |
None` returning an error message or `None`) that wraps whichever of these fits each `QuestionType`
is the shape that fits `form_engine`'s existing style of small, type-dispatching helper functions
(`submitted_text_answer`, `has_submitted_answer` are exactly this shape already).

### 2. A real `django.forms.Form` per page — is it a better fit?

Not examined in isolation above only as a menu option — expanding the honest trade-off. Building
`type("DynamicPageForm", (forms.Form,), {f"question_{q.id}": field_for(q) for q in questions})` (or
using `forms.Form.declared_fields` manipulation / `formset_factory`) gets:

- Free per-field `form.errors[name]` dict, exactly the per-question shape option 3 above wants.
- Free `widget.attrs["class"]` styling hooks, though FLS would still need to pass its Tailwind
  classes through `widget=forms.DateInput(attrs={"class": "..."})` per field — no less markup work
  than hand-rolling the input, just moved into Python.
- Free `min`/`max` wiring via `MinValueValidator`/`MaxValueValidator` on the field, or `attrs={"min":
  ..., "max": ...}` for the native HTML attribute the idea's decision 3 wants anyway.

Against this: `save_answers` (`models.py:310`) is written entirely around raw `post_data` and
`QuestionOption` ids — rewriting it to read from `form.cleaned_data` means every value it writes
changes shape (a `cleaned_data["question_123"]` is already a `date` object for a `DateField`, not
the ISO string `text_answer` wants to store — so the write path would need `str(cleaned_value)`
back out again, a round-trip that gains nothing over just parsing the string directly). The
existing widget partials (`inputs/short_text.html`, `inputs/number.html`, etc.) render with FLS's
own markup, `sr-only` labels, and `read_only`/`existing_answers` wiring that a `forms.Form`'s
auto-generated widget HTML does not know about — using the `Form` only for validation and keeping
the hand-rolled templates as the actual widgets means constructing the `Form`'s fields is pure
overhead: a second type-dispatch table (`QuestionType` → `forms.Field` subclass) that has to be kept
in sync with the first (`QuestionType` → template partial), for no rendering benefit. Given `form_engine`
already reads `QuestionType` for storage-slot decisions (`FREE_TEXT_QUESTION_TYPES`) and for template
dispatch (`question.html`'s `{% if question.type == ... %}` chain), a *third* type-dispatch table
purely for a `forms.Form` field map is a real, avoidable cost. **Honest conclusion: a per-page
`forms.Form` is a legitimate, more "Django-idiomatic" choice, and it is the more mainstream way to
get free per-field errors and centralised clean_<field>() hooks — but for this specific codebase, it
duplicates machinery the two other layers (storage-slot dispatch, template dispatch) already
maintain, and it does not remove the need to write the per-question error template slot regardless.**
A small, question-type-dispatching validate function that plugs into the *existing*
`unanswered_required_on_page`-shaped view flow is less code, not more idiomatic-in-the-abstract but
more idiomatic-for-this-codebase.

### 3. Accessible error patterns for long forms

**WCAG 3.3.1 Error Identification (Level A)** requires that when an input error is detected, the
item in error is identified and the error is described to the user in text. **WCAG 3.3.3 Error
Suggestion (Level AA)** additionally requires that, where known and not a security risk, a
suggestion for correction is provided (e.g. "must be in the format DD/MM/YYYY" rather than just
"invalid"). Both are directly relevant: a per-question error string like "Enter a valid date" meets
3.3.1 on its own; naming the expected format ("Enter a date in the format DD/MM/YYYY") is what lifts
it to 3.3.3.

**The GOV.UK Design System error-summary + error-message pattern** is the most thoroughly documented
version of this and maps closely onto what `form_engine`'s runner already half-does with its single
callout:

- **Error summary**: an `<h2 class="govuk-error-summary__title">There is a problem</h2>` inside a
  container with `role="alert"`, placed at the top of the page's main content (below any
  breadcrumb/back-link, above the page's own `<h1>`), listing every field in error as a link. Each
  link's `href` targets the `id` of the specific input in error — for a single-input question that's
  straightforward; for a radio/checkbox group it targets the first option's `id`. On page load with
  errors present, focus moves programmatically to the summary so a screen-reader or keyboard user
  lands on the list of problems immediately, not wherever focus happened to be.
  ([GOV.UK error summary](https://design-system.service.gov.uk/components/error-summary/))
- **Error message**: sits directly beside/below the specific field, associated to it via
  `aria-describedby` (combined with any hint text's own id, e.g.
  `aria-describedby="field-hint field-error"`), carries a visually-hidden "Error:" prefix so a
  screen reader announces "Error: <message>" even though sighted users just see the red text, and
  the input gets a `--error` style class for the visual red-border cue. The error text used here
  must be **exactly the same string** as the corresponding line in the summary, so a user does not
  see two different descriptions of the same problem depending on where they read it.
  ([GOV.UK error message](https://design-system.service.gov.uk/components/error-message/))

For `form_engine`, the direct implication: `required_answers_error`'s current shape (one string,
one callout, no links) already partially plays the "error summary" role — it names which question
numbers are missing, but doesn't link to them or move focus. Whatever content-validation errors add
should decide whether to extend that same callout into a proper linked summary (each named question
becomes an anchor to `#question_{{ id }}`, focus moves to the callout on the 422 render — the runner
template already does deliberate focus management elsewhere, see `data-runner-page-heading` in
`course_form_page.html:248-266`, so the pattern of "manage focus on render" already exists in this
codebase) or to keep the summary as a plain heads-up and rely solely on per-field error text next to
each input. Either choice should carry both the summary-level and field-level text as the *same
string* per GOV.UK's consistency rule, if both are shown.

### 4. Saving an invalid value: what happens, what other systems do

The idea's own framing (`idea.md`, decision 2: "the person filling the form does not lose their
work") is the FLS-specific instance of a broader, well-documented tension: server-side validation
that runs after the browser's own client-side checks either (a) discards the bad value and treats
the field as blank on re-render, or (b) stores/echoes the bad value back so the person doesn't have
to retype it. FLS has already chosen (b) as its house style for the required-field case — `save_answers`
runs unconditionally before the required check decides whether to 422 (`course_applications/views.py:201-202`,
`learner_interface/views.py:1377-1383`) — so a spec that adds content validation and then silently
discards a rejected value on 422 would be a genuine regression against the project's own established
principle, not a neutral design choice.

The concrete trap this creates, confirmed above: **`<input type="date" value="banana">` renders as
an empty date picker.** The learner who typed `banana` (or a plausible-looking but wrong date like
`31/02/2026`) sees a blank box on the 422 re-render, with no visible trace of what they typed,
unless the error text itself repeats it back to them (e.g. "You entered '31/02/2026' — enter a
valid date"). This is not specific to `form_engine`; it is the HTML5 "value sanitization algorithm"
applied by every conforming browser to `date`, `time`, `datetime-local`, `month`, and `week` input
types alike — a value the microsyntax parser rejects is treated identically to no value at all
([MDN — `<input type="date">`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/date);
cross-browser inconsistency in *how* it's cleared, documented in the
[WHATWG mailing list discussion of incomplete user input in date-like input types](https://lists.whatwg.org/pipermail/whatwg-whatwg.org/2012-September/037280.html)).
Note this is strictly about the native `type="date"` input rendering a server-supplied `value`
attribute — a plain `type="text"` styled to look like a date field would not have this problem, at
the cost of losing the native picker and native client-side format hinting.

Two honest resolutions for the spec to pick between (stated, not decided, per the instruction not to
plan implementation here):

- **Repeat the rejected value only in the error text**, keep the input's `value` attribute empty (or
  omit it) on a validation failure — the person retypes the date, but at least is told what they
  typed and why it was rejected. This keeps the native `<input type="date">` picker working on
  every render, including the 422 one.
- **Fall back the widget to a plain text input carrying the raw rejected string** on a 422 render
  specifically (not swapping the type generally, only for this one re-render), so the invalid text
  is visibly still in the box for the learner to see and correct in place, at the cost of losing the
  native picker for that one round trip.

Neither Django's own form-handling documentation nor the GOV.UK pattern researched above (which
uses a plain `type="text"` for GOV.UK's own date-input component, deliberately avoiding the native
`<input type="date">` picker specifically to sidestep this exact class of problem) definitively
settles this for FLS; it is a genuine product trade-off between "native picker, lose the invalid
text on re-render" and "always-text-input, keep the invalid text, lose the native picker
everywhere, not just on error" that the later spec should decide explicitly rather than by accident.

---

status: ok
reason: codebase read confirms the idea's "no equivalent path" claim is wrong (learner_interface has an identical 422 re-render); external research on Django validators, forms.Form trade-off, GOV.UK/WCAG error patterns, and the confirmed date-input value-sanitization trap are all cited above.
