# Typed question types for form_engine

Forms sometimes need to ask for a date or a time, and `QuestionType` has no way to say so. An author
asking for a date today writes `short_text` and hopes. This adds the question types that are missing,
and with them `form_engine`'s first server-side check on what an answer contains, which is the part
that actually costs something.

## The types to add

`date`, `time`, `email`, `url`, `phone` and `dropdown`.

`date` and `time` are the original ask. They store ISO 8601 in `text_answer` (`YYYY-MM-DD`, `HH:MM`),
which is what the browser submits, what sorts chronologically, and what the input's `value` attribute
must carry back on a revisit.

`email` and `url` are the two typed fields where server-side validation is both trivial and worth
having. `course_applications` collects applicant details, and
`demo_content/functionality_demo_application_form/1. about-you.yaml` already asks for a full name with
`short_text`. Applications want an email address, and many want a portfolio or profile link.
`URLValidator` rejects a schemeless string, so `linkedin.com/in/me` fails unless `https://` is
prepended before validating, the way `forms.URLField` does it. Prepend it.

`phone` renders `<input type="tel">` for the numeric keypad on mobile. The spec should say plainly
that this is a keyboard hint and nothing more. Real phone validation means `libphonenumber` and a
country, which is a different piece of work.

`dropdown` carries the same `QuestionOption` rows and the same `selected_options` storage as
`multiple_choice`, with only the template different, so it needs none of the validation work below.
It earns its place once a question has more than about seven options, where a wall of radio buttons
stops being readable. It is not a solution to the country question.
`research_form_builder_field_types.md` collects the guidance, and the short version is that a plain
`<select>` of 195 entries is nobody's idea of usable. A searchable control is the real answer if that
question ever comes up.

No `datetime`. `datetime-local` carries no timezone, so a stored value would be a bare wall-clock
string in a project running `USE_TZ = True`, ambiguous the moment two respondents sit in different
places. No comparable form builder ships a combined type either. An author who needs both asks for a
date and a time.

## The real work is validation, not types

Adding a scalar type is small: an enum value in `enums.py` and `schema.py`, a template under
`templates/form_engine/inputs/`, and a branch in the dispatch chain in `question.html`. Six types
cost barely more than one.

What costs something is that nothing validates answer content on the server. `submitted_text_answer`
strips whitespace and stores whatever arrived, and `has_submitted_answer` only asks whether it is
non-empty. A POST carrying `question_123=banana` for a date question stores `banana`. That is harmless
today because every free-text type accepts arbitrary text. It stops being harmless the moment a type
claims to be a date, and it is the same work whether one typed field ships or six.

Both form runners already share one validation path. `course_applications/views.py` and the learner
runner in `learner_interface/views.py` both compute `unanswered_required_on_page`, save the answers
the submission did carry, and re-render with `status=422` when something is missing. That path stays;
it gains a second failure mode.

What does not exist is anywhere to put a per-question message. `required_answers_error` is one
form-level string rendered as a callout above the form, and `question.html` has no error element at
all beyond a hidden checkbox-group message that only the runner's Alpine component ever reveals. So
each question gets an error slot, associated to its input with `aria-describedby` and marked
`aria-invalid`, which is what WCAG 3.3.1 asks for and what the file-upload widget already does for
its own errors. Naming the expected format in the message rather than just calling it invalid is what
meets 3.3.3.

A rejected value is not stored. Storing it would leave `banana` sitting in `text_answer` counting as
an answer, which would satisfy the required-question check and let an application through. The page
re-renders carrying what was submitted, so a text-shaped field keeps what the person typed. A
native date or time input will show empty whatever we do, because the browser discards any `value` it
cannot parse. That is not a bug to work around; it is the HTML value-sanitisation rule, documented in
`research_server_side_answer_validation.md`. The error message therefore has to name the rejected
value back to the person, or they have no way of seeing what was wrong with it.

Two traps worth carrying into the spec, both from the same research file. `parse_date` and its
siblings return `None` for a malformed string but raise `ValueError` for a well-formed impossible one
like `2025-02-30`, so a check that only tests for `None` will 500. And `EmailValidator` rejects any
single-label domain other than `localhost`, which will bite in dev before it bites in production.

## Dates and times render as native inputs

One `<input type="date">` per date question, and `<input type="time">` for time. The widget differs
per browser and platform, a calendar popup on desktop Chrome, a wheel on iOS, a Material dialog on
Android, and there is no making them match. All of them submit the same string.

This is a deliberate trade against the accessibility literature, which is worth knowing about rather
than discovering later. GOV.UK, NHS and USWDS all reject the native date input for dates a person
already knows, because the picker opens on the current month no matter what `max` says, so a
date-of-birth question means clicking back through decades. Their answer is a fieldset of three plain
text inputs. That is a composite widget with composite parsing and per-part errors, more work than
every other type in this spec combined, and it is not what we are building now.
`research_native_date_inputs.md` has the full case, so revisiting this later starts from evidence
rather than from scratch.

## min and max

Add `min` and `max` to `FormQuestion` and to the `FormQuestion` pydantic schema, and render them as
the matching HTML attributes. They apply to `date`, `time` and `number`, so a question can refuse a
birth date in 2190 or a rating of 400. `number` gets the bounds it lacks today as a side effect.

These are bounds, not an improvement to the picker. Setting `max` to today does not change where the
calendar opens, so it does nothing for the date-of-birth problem above. The browser enforces them and
the server enforces them again. A `min` in the markup is a hint anyone can edit away, and one the
browser cannot parse is ignored outright rather than failing closed.

## Stored answers need formatting on the way out

Storage does not change. Every answer stays an ISO 8601 string in the existing `text_answer` column.
No migration, no typed columns, no rewriting of read paths.

The cost lands on display. `check_your_answers.html` renders the raw string, so a learner reviewing
their answers sees `1987-03-14`. That needs a helper that formats a stored answer by question type,
reached from a template filter in the `fls_base_filters` library, where the `duration` filter already
sets the pattern of returning something harmless for input it cannot handle. The same helper serves
`QuestionAnswerAdmin.answer_preview`, which is plain Python and cannot call a filter.

What must keep the raw string is every `value="{{ answer.text_answer }}"` in the input templates. The
browser requires the ISO form there, and a formatted date in a `value` attribute renders as an empty
field.

A stored value that will not parse falls back to displaying the raw string. There will be such rows:
answers written before any of this existed, and answers under a question whose `type` an admin
changed after the fact. `research_answer_display_formatting.md` has the full list of display surfaces
and confirms there is no export path or educator-facing view reading `text_answer` today.

## Out of scope, deliberately

**Quiz scoring.** `is_quiz_answer_correct` returns `False` for any question with no correct option,
so the new typed fields score zero in a quiz. No `correct_answer` field, no change to the scoring
strategies. The spec states this plainly so it is not discovered later.

**yes_no and rating/scale.** Both are authoring conveniences over `multiple_choice`, which already
does both, and `CATEGORY_VALUE_SUM` already exists for Likert scales. GOV.UK gives a second reason to
skip `yes_no`. It steers authors toward bare "Yes"/"No" labels where descriptive option text reads
better.

**Matrix and grid questions.** One scale applied across several sub-items in a single question needs a
question × row × column shape that `FormQuestion` and `QuestionOption` do not have. A different data
model, not a `QuestionType`.

**Multi-file upload.** Needs `QuestionAnswerFile` to stop being a `OneToOneField`.

**address, country and signature.** Composite storage, a maintained reference list, and image capture
respectively. None of them is a string in `text_answer`.
