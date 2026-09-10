# Research: question types and validation for application forms

Scope: whether the four existing `form_engine` `QuestionType` values cover the eight application-form
answers, what new types (if any) earn their place, where answer values live, what validation is
missing, and how a conditional question would work. Strategy/scoring/gating (`FormStrategy`, whether
an application form needs a non-scored strategy) is a neighbouring gap, out of scope here, flagged
where it surfaces.

## 1. Type-by-type mapping

| Answer | Maps to | How badly |
| --- | --- | --- |
| `age` (number) | `SHORT_TEXT` | Bad. `text_answer` is an unconstrained `TextField` (`freedom_ls/form_engine/models.py:582`); nothing stops "banana", a negative number, or 400 characters of digits. The only guard today is `required` (`FormQuestion.required`, `models.py:145`). |
| `why_here` (fun/work/own_work/own_company) | `MULTIPLE_CHOICE`, 4 options | Clean fit. Single-select, radios, exactly what `MULTIPLE_CHOICE` is for. |
| `pay_how` (myself/employer/finance/not_sure) | `MULTIPLE_CHOICE`, 4 options | Clean fit. |
| `town` (free text) | `SHORT_TEXT` | Clean fit — genuinely free text. |
| `province` (one of nine) | `MULTIPLE_CHOICE`, 9 options | Works mechanically (`FormQuestion.options`, `QuestionOption`), but nine radio buttons is a lot of fieldset for one question — see §2 on whether that earns a `SELECT`. |
| `working_status` (yes/no/studying) | `MULTIPLE_CHOICE`, 3 options | Clean fit. |
| `travel_distance` (local/200km/anywhere/accommodation) | `MULTIPLE_CHOICE`, 4 options | Clean fit. |
| `heard_about` (google/facebook/dealer/friend/other) + `heard_about_detail` (free text) | `MULTIPLE_CHOICE` (5 options) + `SHORT_TEXT` | The two questions map cleanly on their own; the *relationship* between them (detail is only meaningful when `heard_about` is `other`/`dealer`) has no support in `form_engine` at all. See §5. |
| `nationality` (yes/no) | `MULTIPLE_CHOICE`, 2 options ("Yes" / "No") | Clean fit, and worth stating plainly: this is not a gap. A boolean question is a multiple-choice question with two options; `form_engine` already does this today (see `qa_helpers/management/commands/qa_create_form_question_types.py` and the demo quiz YAML, which use exactly two-option `MULTIPLE_CHOICE` questions throughout). |

Six of the eight answers are exact, un-strained fits for `MULTIPLE_CHOICE`/`SHORT_TEXT` today. The two
genuine rough edges are `age` (no numeric guard) and `province` (many options in one radio group).
`heard_about_detail`'s conditionality is a third, separate issue — not a question-*type* gap, a
question-*sequencing* gap.

## 2. Which new types actually earn their place

Candidates from the brief: `NUMBER`, `SELECT`, `BOOLEAN`.

### `BOOLEAN` — does not earn its place

A yes/no question is `MULTIPLE_CHOICE` with two options, in every respect that matters to
`form_engine`: storage (`selected_options` M2M), submission (`submissions.py`), scoring
(`scoring.is_quiz_answer_correct`, `models.score_category_value_sum`), and reporting
(`reports/indexes.py`). A dedicated `BOOLEAN` type would have to duplicate all four of those paths (or
special-case itself into each) to render as a single Yes/No toggle instead of two radio buttons — for
zero behavioural gain over what two-option `MULTIPLE_CHOICE` already does today. **Do not add it.**
`nationality` and the `working_status`/`yes`/`no` branch both ship as `MULTIPLE_CHOICE`.

### `SELECT` — a rendering hint, not a new type, and not needed yet

A dropdown is `MULTIPLE_CHOICE` under a different `<select>` skin: same single-selection semantics,
same `QuestionOption` rows, same `selected_options` storage, same scoring, same reporting. Nothing in
`submissions.py`, `scoring.py`, or `reports/indexes.py` would need to branch on it — every one of those
already keys off `question.type in FREE_TEXT_QUESTION_TYPES` (`form_engine/enums.py:22`) or, for
scoring, off `selected_options` directly (`models.py:365-369`), neither of which cares how the options
were drawn on screen. The only place that *would* need to know is the `form-question` /
`form-input-*` partials in `course_form_page.html`, which currently dispatch on the literal string
`question.type` (`course_form_page.html:133-143`) — so even as a hint, it needs *some* signal in the
template layer, whether that is a new `QuestionType.SELECT` value or a separate rendering-hint field.

There is no `<select>` house component in `templates/cotton/` today (checked; none exists), so either
path costs one new template partial. Nine provinces is not an unreasonable radio fieldset — the runner
page already gives a question its own scrollable card, and none of the demo content or QA fixtures use
more than four or five options per question, but nothing about the render breaks past nine. **Recommend
deferring `SELECT`.** Ship `province` as `MULTIPLE_CHOICE` with nine options for the first form. If a
later form makes the radio list genuinely unusable, add `SELECT` as a rendering hint on
`MULTIPLE_CHOICE` (an author-facing flag, e.g. `render: select`, read only by the template), not as a
new `QuestionType` — that keeps every other module exactly as it is today.

### `NUMBER` — earns its place, and it's cheap

`age` needs *something* better than an open `TextField`. `NUMBER` is the one candidate that is a
genuine new `QuestionType` value (its answer still stores as `text_answer`, not `selected_options`, so
it has to join `FREE_TEXT_QUESTION_TYPES`), but the frozenset is the single seam every free-text-aware
module already reads through:

- `submissions.py:23-32` (`has_submitted_answer`, `submitted_text_answer`) — generic over the set, no change beyond membership.
- `models.py:307` (`save_answers`) — generic over the set, no change beyond membership.
- `models.py:537` (`get_incorrect_quiz_answers`) — generic over the set, no change beyond membership.
- `reports/indexes.py:563,627` and `reports/gather.py:472` — generic over the set, no change beyond membership.

So the entire cost is:
1. `form_engine/enums.py`: add `NUMBER = "number"` to `QuestionType`, add it to `FREE_TEXT_QUESTION_TYPES`.
2. `form_engine/schema.py`: add `NUMBER` to the pydantic `QuestionType` `StrEnum` (schema.py:13-19), so authors can write `type: number`.
3. `course_form_page.html`: one new `form-input-number` partial (an `<input type="number">` in place of `form-input-short-text`'s `<input type="text">`) and one new `{% elif question.type == "number" %}` branch in `form-question` (course_form_page.html:133-143), otherwise it falls into the `ERROR! UNHANDLED FORM TYPE` branch (line 142).

`<input type="number">` is what actually stops "banana" — native browser validation on a numeric
field, at effectively no cost given the seam above. It does **not** stop an implausible number
(`age: 999`, `age: -4`); see §4 for where that plausibility check belongs, and why it's a separate,
optional addition rather than part of the type itself. **Recommend adding `NUMBER`** — it is the
minimal honest new type, and it is the one candidate where "genuinely new type" and "cheap" are both
true at once.

Net recommendation: **one new type, `NUMBER`.** `SELECT` and `BOOLEAN` are declined for this form.

## 3. Where answer values live

`QuestionAnswer` (`models.py:572-593`) has exactly two storage slots:

- `selected_options` — `ManyToManyField(QuestionOption)`, for `MULTIPLE_CHOICE` and `CHECKBOXES`.
- `text_answer` — `TextField`, for anything in `FREE_TEXT_QUESTION_TYPES`.

There is no third slot, and there should not be one for `NUMBER`: a number question's answer is still
free text as far as storage is concerned — the row holds `"34"` in `text_answer`, exactly like
`SHORT_TEXT` holds a town name. The type only changes what markup the browser renders and what native
constraint it applies; it does not change which column the answer lands in. This is why `NUMBER` must
join `FREE_TEXT_QUESTION_TYPES` (`enums.py:22`) rather than get a new branch of its own — the frozenset
*is* the "text vs. options" switch, and every module that needs to know which storage slot a question
uses reads it from there, not from a hardcoded type list:

- `submissions.py:30` — `has_submitted_answer` branches on the frozenset to decide whether "submitted"
  means non-blank text or a non-empty option list.
- `models.py:307` — `save_answers` branches on the frozenset to decide which field to write.
- `models.py:537` and `reports/indexes.py:563,627` and `reports/gather.py:472` — all branch on the
  frozenset to *exclude* free-text questions from quiz scoring/reporting, since a `text_answer` has no
  `correct` flag to score against.

**A new type must be added to exactly one place to get free-text storage semantics: the
`FREE_TEXT_QUESTION_TYPES` frozenset in `enums.py`.** Everywhere else that matters already reads
through it. The one place that does *not* read through the frozenset, and so needs its own explicit
branch regardless of storage, is the template's `question.type ==` dispatch in `course_form_page.html`
— because that dispatch chooses *markup*, not storage, and `NUMBER` and `SHORT_TEXT` render
differently even though they store identically.

## 4. Validation

Today there is exactly one validation rule, and it lives in the view: `form_fill_page`
(`freedom_ls/learner_interface/views.py:1037`) computes `unanswered_required` by checking
`question.required and not has_submitted_answer(...)` (views.py:1098-1101) against every question on
the page, saves whatever *was* submitted regardless (views.py:1106, so a rejected page doesn't lose
good answers), and re-renders the same template with `status=422 if required_answers_error else 200`
(views.py:1243). There is no author-time (pydantic) or model-level (`clean()`/constraint) validation of
an individual answer's *content* anywhere in `form_engine` — `required` is presence-only.

What this application form minimally needs, beyond `required`, which it already has:

- **`age` as plausible, not just present.** `<input type="number">` (§2) gets native "this must be a
  number" enforcement for free. A range check (`age` between, say, 16 and 120) is a step further:
  nothing in `FormQuestion` carries author-configurable bounds today, and adding `min_value`/
  `max_value` fields (model + pydantic schema + a migration) is a real, if small, feature — not
  something the existing four types need elsewhere. **Recommend deferring range validation**, per "Don't
  build functionality that is not explicitly requested" (`CLAUDE.md`): ship `type: number` with no
  author-configurable bounds for the first form, and treat a numeric range as a follow-up if the first
  form's data shows it's actually needed. If it is needed later, it is a view-level check (parse the
  submitted `text_answer`, reject out-of-range the same way `unanswered_required` rejects blanks today),
  not a model or pydantic addition — the answer is still just text.
- **A max length on free text** (`town`, `heard_about_detail`) — `TextField` has no length limit
  server-side. Not a real risk for an applicant-facing screening form (nobody pastes a novel into "what
  town do you live in"); not worth adding for this form.
  A required-field pass before submit already exists and needs no change — `unanswered_required` /
  `required_answers_error` (views.py:1098, 1121, 1243) is the exact mechanism the brief asks about, and
  it already returns HTTP 422 with the page re-rendered, listing what's missing.

**Where new per-question validation should live, if a future form needs it:** the view, following the
`unanswered_required` pattern exactly — collect failures across all of a page's questions, save what
validates, re-render the same template with the same failures surfaced, and return 422. Not the
pydantic schema (that validates the *author's* YAML at content-load time, not a *learner's* submitted
answer — it has no access to `post_data`), and not the model (`QuestionAnswer.save()` has no
`clean()`/constraint today, and adding one there would mean every caller of `save_answers` has to
handle a raised exception instead of the current save-what's-valid, list-what's-missing flow).

The house convention for the status code: `claude_plugins/django-stack/skills/htmx/SKILL.md:63-66`
("**422** for validation errors on HTMX requests"). `form_fill_page` already follows the spirit of
this for a plain (non-`HX-Request`) form POST — the runner page is native-form-submit, not an
`hx-post`, and `views.py:1243` still returns 422 on a rejected submission, re-rendering the full page
rather than a partial. Any new answer-level validation on this form should do the same: 422 on the
full page response, not just on the required-field check.

## 5. Conditional questions

Nothing in `form_engine` supports conditional display. `FormQuestion` (`models.py:129-173`) has no
"depends on", "shown if", or similar field; `FormPage.children()` (`models.py:91-102`) always returns
every question and content block on the page in `order`, unconditionally. There is no mechanism to
short-circuit at authoring time or at render time based on another question's answer.

`claude_plugins/fls-dev/skills/alpine-js/SKILL.md`'s component inventory has nothing that does
"reveal a sibling field based on a selection" — the closest entries (`dropdownMenu`, `modal`,
`coursePart`) are unrelated toggle/expand patterns, not conditional-reveal-by-answer.

Three honest options, in order of cost:

1. **Always show `heard_about_detail`.** Zero mechanism, `required: False`. The applicant sees an
   optional "tell us more" box regardless of what they picked for `heard_about`. Mildly odd for someone
   who picked `google`, harmless.
2. **A small, form-specific Alpine reveal, no server round-trip.** Wrap the two questions' markup with
   `x-show` keyed off the radio group's checked value. This is buildable without touching `form_engine`
   at all — but it has to be written against the two *specific* question UUIDs it applies to, because
   the generic `form-question` partial has no concept of "this question's visibility depends on that
   one's answer." That coupling is a one-off, template-level thing, not a `form_engine` feature.
3. **Defer conditionals entirely** as a `form_engine` capability. A generic "depends_on" mechanism
   (author-facing field on `FormQuestion` + pydantic schema + render-time evaluation) is a real feature,
   speculative against a single first use, and exactly what "Don't build functionality that is not
   explicitly requested" argues against.

**Recommendation: option 3 for `form_engine` itself, with option 2 available downstream if needed.**
The brief already notes the first form's actual questions ship downstream, not in FLS — which means the
`heard_about` → `heard_about_detail` coupling is a downstream template concern too. FLS is "designed to
be extended and customized" (`CLAUDE.md`); a downstream project that wants the Alpine reveal can
override `course_form_page.html`'s `form-question` partial for its own form (or add a small
`hx-headers`-free Alpine snippet around its own two known question UUIDs) without FLS needing a
generic conditional-question feature. For the illustrative YAML below, `heard_about_detail` ships as
option 1 — always visible, not required — since that's the only option `form_engine` supports without
any new code, on either side of the FLS/downstream boundary.

## 6. Author-facing YAML

In `demo_content` format (see `demo_content/functionality_demo_end_with_quiz/5. quiz/1. page.yaml` and
`.../form.md`), under the recommended type set (`MULTIPLE_CHOICE`, `SHORT_TEXT`, and the new `NUMBER`).
Illustrating the mechanism only — content is not FLS's to carry.

`applicant details/form.md` (top-level `Form`; note `strategy` has no non-scored option today —
neither `CATEGORY_VALUE_SUM` nor `QUIZ` describes an ungraded screening form. That's a `FormStrategy`
gap, not a question-type one; out of scope here, flagged for whoever owns strategy/completion):

```yaml
---
content_type: FORM
strategy: CATEGORY_VALUE_SUM  # placeholder — see FormStrategy gap note above
title: Course Application
uuid: 6f1a2b3c-0000-4000-8000-000000000001
---

Tell us a bit about yourself before we set up your place on the course.
```

`applicant details/1. page.yaml` (one `FormPage`, all eight questions):

```yaml
---
content_type: FORM_PAGE
title: About you
uuid: 6f1a2b3c-0000-4000-8000-000000000002
---
question: How old are you?
type: number
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000010
---
question: Why are you interested in this course?
type: multiple_choice
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000011
options:
  - text: For fun
    value: fun
    uuid: 6f1a2b3c-0000-4000-8000-000000000012
  - text: For work
    value: work
    uuid: 6f1a2b3c-0000-4000-8000-000000000013
  - text: To start my own work
    value: own_work
    uuid: 6f1a2b3c-0000-4000-8000-000000000014
  - text: To grow my own company
    value: own_company
    uuid: 6f1a2b3c-0000-4000-8000-000000000015
---
question: How will you pay for the course?
type: multiple_choice
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000020
options:
  - text: I'll pay myself
    value: myself
    uuid: 6f1a2b3c-0000-4000-8000-000000000021
  - text: My employer will pay
    value: employer
    uuid: 6f1a2b3c-0000-4000-8000-000000000022
  - text: I'll need to finance it
    value: finance
    uuid: 6f1a2b3c-0000-4000-8000-000000000023
  - text: Not sure yet
    value: not_sure
    uuid: 6f1a2b3c-0000-4000-8000-000000000024
---
question: What town do you live in?
type: short_text
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000030
---
question: Which province is that in?
type: multiple_choice
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000031
options:
  - text: Eastern Cape
    value: eastern_cape
    uuid: 6f1a2b3c-0000-4000-8000-000000000032
  - text: Free State
    value: free_state
    uuid: 6f1a2b3c-0000-4000-8000-000000000033
  - text: Gauteng
    value: gauteng
    uuid: 6f1a2b3c-0000-4000-8000-000000000034
  - text: KwaZulu-Natal
    value: kwazulu_natal
    uuid: 6f1a2b3c-0000-4000-8000-000000000035
  - text: Limpopo
    value: limpopo
    uuid: 6f1a2b3c-0000-4000-8000-000000000036
  - text: Mpumalanga
    value: mpumalanga
    uuid: 6f1a2b3c-0000-4000-8000-000000000037
  - text: Northern Cape
    value: northern_cape
    uuid: 6f1a2b3c-0000-4000-8000-000000000038
  - text: North West
    value: north_west
    uuid: 6f1a2b3c-0000-4000-8000-000000000039
  - text: Western Cape
    value: western_cape
    uuid: 6f1a2b3c-0000-4000-8000-00000000003a
---
question: Are you currently working?
type: multiple_choice
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000040
options:
  - text: "Yes"
    value: "yes"
    uuid: 6f1a2b3c-0000-4000-8000-000000000041
  - text: "No"
    value: "no"
    uuid: 6f1a2b3c-0000-4000-8000-000000000042
  - text: I'm studying
    value: studying
    uuid: 6f1a2b3c-0000-4000-8000-000000000043
---
question: How far are you willing to travel for the course?
type: multiple_choice
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000050
options:
  - text: Local only
    value: local
    uuid: 6f1a2b3c-0000-4000-8000-000000000051
  - text: Up to 200km
    value: 200km
    uuid: 6f1a2b3c-0000-4000-8000-000000000052
  - text: Anywhere
    value: anywhere
    uuid: 6f1a2b3c-0000-4000-8000-000000000053
  - text: Anywhere, if accommodation is provided
    value: accommodation
    uuid: 6f1a2b3c-0000-4000-8000-000000000054
---
question: How did you hear about us?
type: multiple_choice
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000060
options:
  - text: Google
    value: google
    uuid: 6f1a2b3c-0000-4000-8000-000000000061
  - text: Facebook
    value: facebook
    uuid: 6f1a2b3c-0000-4000-8000-000000000062
  - text: A dealer
    value: dealer
    uuid: 6f1a2b3c-0000-4000-8000-000000000063
  - text: A friend
    value: friend
    uuid: 6f1a2b3c-0000-4000-8000-000000000064
  - text: Other
    value: other
    uuid: 6f1a2b3c-0000-4000-8000-000000000065
---
question: If "a dealer" or "other" — who or where, specifically?
type: short_text
required: false
uuid: 6f1a2b3c-0000-4000-8000-000000000070
---
question: Are you a South African citizen?
type: multiple_choice
required: true
uuid: 6f1a2b3c-0000-4000-8000-000000000080
options:
  - text: "Yes"
    value: "yes"
    uuid: 6f1a2b3c-0000-4000-8000-000000000081
  - text: "No"
    value: "no"
    uuid: 6f1a2b3c-0000-4000-8000-000000000082
```

The YAML reads cleanly with exactly one new type (`number`, on the age question) and everything else
already-existing `multiple_choice`/`short_text` — confirming the type set in §2 rather than straining
against it. The one visibly awkward line is the always-shown detail question's wording ("If 'a dealer'
or 'other' — who or where, specifically?"), which is doing by hand what conditional display would
otherwise do — the cost of deferring §5, made concrete.

status: ok
