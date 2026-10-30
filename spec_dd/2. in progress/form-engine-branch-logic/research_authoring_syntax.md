# Research: how a branch-logic condition should be *written* in a FLS form file

Scope: author-facing syntax and its validation only — not the runtime evaluation model, not the
learner-facing UI, not a visual editor's internals. Written against the real
`demo_content/functionality_demo_application_form` example, for the "will your employer pay for
this course?" case (application forms + surveys; explicitly not quizzes in v1).

FLS source read for this research: `freedom_ls/form_engine/schema.py`, `freedom_ls/form_engine/models.py`,
`freedom_ls/content_base/schema.py`, `demo_content/functionality_demo_application_form/{form.md,1. about-you.yaml,2. supporting-documents.yaml}`,
`claude_plugins/fls-content/skills/content-types/{SKILL.md,resources/form-files.md}`.

---

## 1. How comparable file-based / declarative systems express conditions

### XLSForm / ODK `relevant` — the closest analogue

XLSForm is a spreadsheet format (compiled by `pyxform` to ODK's XML XForm) where each row is a
question with a `name` column (the stable, author-chosen identifier) and a `relevant` column
holding a boolean **XPath-ish expression string**. A previously-named question is referenced by
wrapping its `name` in `${}`:

```
${likes_pizza} = 'yes'
```

For a multi-select ("select_multiple") question, equality does not work against one selection
out of several, so XLSForm provides a dedicated function:

```
selected(${favorite_topping}, 'cheese')
```

The `constraint` column reuses the same expression language for validating the current field
against itself, using `.` for "this field's value":

```
. <= 150
```

with an optional plain-text `constraint_message` column carrying the author-facing error shown to
the *respondent* (not the form author) when the constraint fails. Formulas draw on XPath function
and operator syntax (`+ * div` etc.). [ODK Docs — XLSForm](https://docs.getodk.org/xlsform/),
[XLSForm reference docs](https://xlsform.org/en/).

This is the single closest analogue to FLS's situation: a spreadsheet/text row-based format,
authored by non-programmers, referencing sibling questions by a stable name, expressing the
condition as one short string per row.

### SurveyJS `visibleIf` / `enableIf` — string expressions inside JSON

SurveyJS's JSON form definitions attach a **string expression** to a `visibleIf` (or `enableIf`,
`requiredIf`) property on a question/panel/page. Questions are referenced by their `name` in curly
braces:

```javascript
"visibleIf": "{age} >= 21"
"enableIf": "{phone} notempty"
```

Multi-value (checkbox) answers get a `contains` operator rather than `=`, because a checkbox
answer is an array:

```javascript
"visibleIf": "{selectedOptions} contains 'option1'"
```

and arithmetic/boolean composition is supported in the same string:

```
"({rank1} + {rank2} + {rank3}) > 21 and {isLoyal} = 'yes'"
```

SurveyJS documents this as "SurveyJS supports comparison, logical and arithmetic operators… A
survey parses and runs all expressions on startup." [SurveyJS — Conditional Logic and Dynamic
Texts](https://surveyjs.io/form-library/documentation/design-survey/conditional-logic).

### JSON Schema `if`/`then`/`else` and `dependentSchemas` — no expression language at all

JSON Schema's conditional keywords apply an entire **subschema**, not a boolean test on a single
field: `if` is itself a schema; if the instance validates against it, `then` is required to also
validate (else is ignored), and vice-versa for `else`.
`dependentSchemas` applies a subschema only when a given property is *present* on the instance
(no value comparison — presence only). Both keywords are pure structured data: there is no
expression string anywhere in JSON Schema. [json-schema.org — Conditional schema
validation](https://json-schema.org/understanding-json-schema/reference/conditionals),
[learnjsonschema.com — `if`](https://www.learnjsonschema.com/2020-12/applicator/if/),
[learnjsonschema.com — `dependentSchemas`](https://www.learnjsonschema.com/2020-12/applicator/dependentschemas/).

`react-jsonschema-form` (RJSF) originally only supported the older, narrower `dependencies`
keyword (`billing_address` appears only if `credit_card` is present), then added full
`if`/`then`/`else` support once JSON Schema draft-07 defined it — evaluating the `if` subschema
against current form data and merging in the matching branch before rendering.
[RJSF — Dependencies](https://rjsf-team.github.io/react-jsonschema-form/docs/json-schema/dependencies/),
[RJSF issue #850 — implement if/then/else](https://github.com/rjsf-team/react-jsonschema-form/issues/850),
[DeepWiki — RJSF conditional schema resolution](https://deepwiki.com/rjsf-team/react-jsonschema-form/6.4-conditional-schema-resolution-(ifthenelse)).

### JsonLogic — structured data that *is* an expression tree

JsonLogic represents boolean/arithmetic logic as nested JSON objects, e.g. `{"var": "a"}` reads a
value out of the data context (`{"var": ["a", 1]}` supplies a default), and operators combine as
nested objects:

```json
{ "and" : [
    {"<" : [ { "var" : "temp" }, 110 ]},
    {"==" : [ { "var" : "pie.filling" }, "apple" ] }
]}
```

against data `{"temp": 100, "pie": {"filling": "apple"}}`. [JsonLogic — `var` operator and
examples](https://github.com/nadirizr/json-logic-py). This is the "structured data that encodes an
expression tree" middle ground: no string to parse, but still Turing-adjacent nesting rather than a
flat mapping.

### CEL (Common Expression Language)

CEL is Google's small, sandboxed expression language, "fast, portable, and safe to execute…
extensible, platform independent, formally verifiable, and optimized for compile-once/evaluate-many,"
explicitly positioned as the choice "when a fully sandboxed scripting language is too resource
intensive." Textual syntax resembles C/JS: `has(account.user_id) || has(account.gaia_id)`,
`size(account.emails) > 0`. [cel.dev — CEL overview](https://cel.dev/overview/cel-overview),
[google/cel-spec](https://github.com/google/cel-spec). CEL is a string-expression system with a
formal grammar and a safety design point built in from the start (used for Kubernetes admission
policies and Envoy access rules), unlike a general-purpose language pressed into safety later.

### Formily / react-jsonschema-form — string expressions layered onto JSON Schema

Formily's `x-reactions` attaches JavaScript-like template expressions to fields for conditional
show/hide and value computation, e.g. `'{{$deps[0] !== undefined ? $self.value * $deps[0] :
$target.value}}'`. [alibaba/formily — linkages
docs](https://github.com/alibaba/formily/blob/formily_next/docs/guide/advanced/linkages.zh-CN.md).
This is notable as the trajectory point: RJSF and JSON Schema itself stayed **structured**
(`if`/`then`/`else`, `dependencies`), but ecosystem tools built *on top* of JSON Schema (Formily,
`react-jsonschema-form-conditionals`) reached for a **string expression escape hatch** once authors
needed logic the structured keywords couldn't express economically.

### GitHub Actions `if:` — a mainstream YAML-embedded expression language, warts included

GitHub Actions embeds a small expression language directly in YAML, delimited by `${{ }}`
elsewhere in a workflow but **optionally omittable inside `if:`** specifically:

```yaml
if: startsWith(github.ref, 'refs/tags/')
```

Property access uses `.` on named "contexts" and silently evaluates a nonexistent property to an
empty string rather than erroring — a design choice that trades an authoring error for silent
wrong behaviour. Because `{` and `}` are YAML/template-significant, GitHub Actions needs its own
escaping convention for literal braces (the `format` function escapes braces by doubling them, so
`format('{{Hello {0}!}}', 'Mona')` produces `'{Hello Mona!}'`) and a documented dedicated GitHub
issue exists purely because `if:`'s "you can omit `${{ }}`" rule interacts badly with a leading
negation operator (`if: !startsWith(...)` fails in ways that `if: ${{ !startsWith(...) }}` does
not). [GitHub Docs — Evaluate expressions in workflows and
actions](https://docs.github.com/actions/reference/evaluate-expressions-in-workflows-and-actions),
[GitHub Docs — Contexts](https://docs.github.com/en/free-pro-team@latest/actions/reference/context-and-expression-syntax-for-github-actions),
[github/docs issue #3001 — incorrect info about expression syntax for `if`
conditionals](https://github.com/github/docs/issues/3001). This is exactly the kind of ergonomic
cost — an author-invisible dialect switch depending on where in the YAML the string sits, plus a
brace-escaping micro-language layered on top of YAML's own — that a string-expression design has
to either accept or design its way around.

### Home Assistant condition blocks — the clearest counter-example (structured, not a string)

Home Assistant's YAML automations express a condition as **structured data**, not an expression
string, for the common cases, while keeping a `template` condition as an escape hatch for anything
the structured vocabulary can't say:

```yaml
conditions:
  - condition: state
    entity_id: device_tracker.paulus
    state: "home"
  - condition: numeric_state
    entity_id: sensor.temperature
    below: 20
```

Multiple conditions in a list are implicitly ANDed ("Conditions are `and` by default"); explicit
combinators are their own structured blocks:

```yaml
conditions:
  - condition: or
    conditions:
      - condition: state
        entity_id: device_tracker.paulus
        state: "home"
      - condition: numeric_state
        entity_id: sensor.temperature
        below: 20
```

and the escape hatch, when structured data genuinely cannot express the check, drops to a Jinja
template string:

```yaml
conditions:
  - condition: template
    value_template: "{{ (state_attr('device_tracker.iphone', 'battery_level')|int) > 50 }}"
```

[Home Assistant Docs — Conditions](https://www.home-assistant.io/docs/scripts/conditions/). This
is the strongest evidence in this survey for "author most conditions as a small structured
vocabulary, and reserve a string escape hatch — if one is ever needed at all — for the rare case
the vocabulary can't reach," rather than making every condition, however simple, a string to parse.

### IMS QTI `preCondition` / `branchRule` — structured XML, explicitly excluded from FLS's v1 scope

QTI's `preCondition` element "sets the conditions that need to be met for an assessmentItem or
assessmentSection to be displayed," and `branchRule` "contains a rule … for setting an alternative
target as the next item or section" — both evaluated via QTI's own nested XML expression elements
(`variable`, `baseValue`, `match`, `equal`, etc.), i.e. structured markup, not a string. [IMS QTI
v2.2 Implementation
Guide](https://www.imsglobal.org/question/qtiv2p2/imsqti_v2p2_impl.html). The full worked XML
example (`examples/tests/rtest13.xml`) referenced by the guide was not independently retrievable
during this research (404 on the historical GitHub mirror), so the exact expression nesting is
reported at the level the specification text itself states, not quoted verbatim. QTI's branching
model is considerably more powerful than what FLS needs for v1 — it can jump execution to an
arbitrary later section, not just show/hide a question on the same or a later page — which is
exactly why the user's brief marks quizzes (and by extension QTI-style branching) out of scope for
the first version.

---

## 2. The central fork: expression string vs structured data

Concretely, for FLS, the fork is between something like

```yaml
when: employer_pays == "yes"
```

and

```yaml
when:
  question: employer_pays
  equals: "yes"
```

| Concern | Expression string | Structured mapping |
|---|---|---|
| Authoring | One familiar-looking line; scales smoothly to `and`/`or`/arithmetic without inventing new keys (XLSForm, SurveyJS both do this) | More YAML to type for even the simplest case; boolean combinators need their own nested shape (Home Assistant's `condition: and` block) |
| Pydantic validation | The schema can only say "this must be a string" — everything about *meaning* (does the referenced question exist? is the type comparable?) has to be checked by a second-pass parser/interpreter, not by Pydantic's own field types | Each piece (`question`, `equals`) is its own typed field; Pydantic validates structure and the FLS import step can validate meaning field-by-field, the same way `Form.validate_quiz_fields` already cross-checks `strategy` against `quiz_show_incorrect`/`quiz_pass_percentage` |
| Naming the mistake in an error | Error has to say *where in the string* the reference is wrong (line/column offset into a one-line YAML scalar) — harder to make friendly | Error can say "the `question:` key of the `when:` on page 2 names `employer_pay`, but no question in this form has that key" — exactly the shape of FLS's existing `file_path`-quoting `ValueError`s |
| Future visual editor | Round-tripping a parsed-then-regenerated expression string risks losing the author's exact formatting/whitespace, and building a UI that edits a string safely means embedding (part of) a parser in the UI too | A structured mapping already *is* the UI's data model — a picker for `question`, a picker for `equals`'s value — no parser needed on either side |
| Diffing in git | A single-line string diffs as one line changing, which can hide that only one operand changed (e.g. `employer_pays == "yes"` → `employer_pays == "no"` reads as a small diff either way) | A structured mapping diffs key-by-key, so `equals: "yes"` → `equals: "no"` is exactly as visible, but nesting for `and`/`or` produces bigger diffs for compound conditions |
| Security of evaluation | Needs a real "no arbitrary code execution" evaluator (see §5) with its own attack surface and maintenance burden, however small | No expression evaluator exists at all — the interpreter is a few lines of Python pattern-matching known keys, nothing an author-supplied string can drive into unintended code paths |

**Evidence of regret in one direction.** JSON Schema's own maintainers have an open, years-long
issue about how hard genuinely conditional (`if`/`then`/`else` / `oneOf`) structured schemas are to
read and reason about even *without* a string language layered in — "one difficulty … is that
cause and effect are not clear" — which is a caution against assuming structured data is free of
authoring cost just because it avoids a parser. [json-schema-spec issue #64 — conditional selection
of alternate schemas](https://github.com/json-schema-org/json-schema-spec/issues/64). Conversely,
GitHub Actions' `if:` (§1) shows the concrete costs a string-expression choice pays in practice:
brace-escaping rules borrowed from the templating layer, and a documented bug class where
whether-or-not to wrap the expression in `${{ }}` silently changes parsing behaviour. The clearest
directional evidence is Home Assistant choosing structured data for its default authoring surface
and keeping a string (Jinja template) condition only as a fallback — i.e., when a project designs
a YAML-authored condition system from scratch today, aimed at non-programmer authors, it reaches
for structured data first and adds a string escape hatch later, not the other way round.

---

## 3. Referencing another question — the missing stable identifier

FLS's `FormQuestion` (and `QuestionOption`) carries a `uuid: str | None` (see
`freedom_ls/content_base/schema.py:31`, `freedom_ls/form_engine/schema.py:97`) but — per the
`fls-content` skill's own conventions doc — that `uuid` is **written by tooling on first save and
never hand-created**. A condition written as `uuid: 0a73990c-d232-4da1-91ba-84ed30c683b9` (an
actual uuid from `demo_content/functionality_demo_application_form/1. about-you.yaml`) is
unreadable to an author re-reading their own form a month later, and cannot be typed in a first
draft before the file has ever been saved. FLS has no existing human-readable, author-chosen,
stable identifier field on `FormQuestion` at all — this is a genuine gap the branch-logic feature
must fill, not something to route around.

Other systems' answers to "how do you name a referencable field":

- **XLSForm's `name` column** — "The name column specifies the unique variable name for that
  entry. No two entries can have the same name," constrained to start with a letter/underscore and
  contain only letters, digits, hyphens, underscores and periods, case-sensitive. [XLSForm
  reference](https://xlsform.org/en/). `pyxform` (the XLSForm compiler) treats a duplicate `name`
  as an authoring error to catch at compile time, and has an explicit escape hatch
  (`allow_choice_duplicates` in the settings sheet) for the one case — duplicate *choice list*
  names, not question names — where the tool would otherwise reject something valid; pyxform's own
  issue tracker records the duplicate-name message being confusing enough to warrant a fix.
  [XLSForm/pyxform issue #373 — duplicate choice name message is
  confusing](https://github.com/XLSForm/pyxform/issues/373).
- **SurveyJS's `name`** — the same role, referenced via `{name}` inside `visibleIf`/`enableIf`
  strings (§1); SurveyJS does not appear to separate a "display label" from the referencable name
  the way Qualtrics does (below).
- **Qualtrics' `QID` vs export tag** — Qualtrics deliberately splits the two concerns FLS is
  conflating in `uuid` and the proposed key: `QID` (e.g. `QID2`) is the **internal, permanent**
  identifier, assigned once and never changeable — "the QID is considered the only
  unique/stable identifier of a question" for API and piped-text purposes — while the
  **export tag** (e.g. `Q1`) is a separate, author-editable label shown in the UI and used in
  exports, which *can* be renamed after the fact without breaking anything that pins to the QID.
  [Qualtrics Community — Be wary of recoding your question
  IDs](https://community.qualtrics.com/survey-platform-before-march-2021-56/be-wary-of-recoding-your-question-ids-13700),
  [Qualtrics Community — accessing question export tags via
  API](https://community.qualtrics.com/qualtrics-api-13/accessing-question-export-tags-via-api-32739).
  This maps directly onto FLS's existing split: `uuid` already plays Qualtrics' QID role (silent,
  permanent, machine-assigned); what's missing is Qualtrics' export-tag role — an author-facing,
  editable label — which is exactly what a new `key` field on `FormQuestion` would be.
- **Google Forms' opaque `itemId`** — item IDs are hexadecimal strings ("8-digit hex", e.g.
  `5d9f9786`) generated by Google, carrying no author-chosen meaning at all, and Google's own
  guidance is to treat the format as opaque and subject to change. [Google Forms API — item
  reference](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms),
  [Report: rule of item IDs for questions of Google
  Forms](https://gist.github.com/tanaikech/f391fd4d596d45bb846d374ff0ded695). This is the
  cautionary case for FLS's *existing* `uuid` field used as a reference target: it is exactly as
  opaque as Google's `itemId`, which is precisely why it is unsuitable as the thing an author types
  into a condition.

What happens when a name changes or collides, across these systems, converges on the same two
answers: (1) **uniqueness is enforced at import/compile time**, with the error naming the
duplicate — pyxform's `unique_names` validator does this for XLSForm — and (2) **renaming an
export-facing/author-facing name is allowed and is the author's problem to keep consistent**,
while the *permanent* internal id (QID, FLS's `uuid`) never changes and is never what the author
edits by hand.

### Referencing a specific option: `value`, `text`, or its own uuid?

`QuestionOption` (`freedom_ls/form_engine/schema.py:90-101`) has three candidate handles: `text`
(display copy — "From a friend or colleague"), `value` (the author-chosen stored value — e.g.
`"yes"`/`"no"`, or `"word_of_mouth"`/`"search"` in the real about-you.yaml), and `uuid` (opaque,
tool-written, same objection as above). Only `value` is designed, in FLS's existing schema, to be
a **stable, author-chosen, machine-comparable token** — it is what the scoring strategies already
read (`score_category_value_sum` parses `option.value` as an int; `is_quiz_answer_correct` compares
against it). `text` is explicitly *display* copy an author will reword for clarity without meaning
to change behaviour — XLSForm's own `selected(${q}, 'cheese')` (§1) matches this precedent exactly:
it references the choice's stable `value`-equivalent (its `name` in the choices sheet), never its
display label. Referencing by `value`, not `text` or `uuid`, is therefore the only one of the three
that is stable under the edit an author is most likely to make (rewording an option) and readable
without a lookup (unlike `uuid`).

---

## 4. Authoring-time validation

FLS already validates its whole content tree with Pydantic at import time, and its own
`model_validator`s quote `file_path` in the raised `ValueError` (`Form.validate_quiz_fields`,
`freedom_ls/form_engine/schema.py:54-77`, e.g. `f"quiz_show_incorrect is required when strategy is
QUIZ (in {self.file_path})"`). A condition-validation step should follow the same convention: name
the file, name the offending value, and say what would fix it. Concretely, the import step should
catch:

- **Dangling reference** — `when: {question: employer_pay, equals: "yes"}` where no question in
  the form has `key: employer_pay` (typo for `employer_pays`). Error should name the typo'd key,
  the file it appeared in, and — ideally — the nearest valid key, the way a good compiler suggests
  "did you mean". XLSForm's own tooling reports a bad `${...}` reference as a hard compile error
  rather than silently treating it as blank.
- **Forward reference (a condition naming a question on a later page)** — for FLS's use case
  (progressively revealing questions as a learner fills a form in), a condition can only sensibly
  depend on a question the learner has *already answered*, i.e. on an earlier page (or earlier in
  the same page's ordering) than the conditional one. QTI's `branchRule` (§1) is the counter-case
  where forward jumps are the entire point — but that is explicitly out of scope here. The importer
  should reject (not silently allow or silently ignore) a condition naming a question later in the
  form's page order, with the error naming both pages.
- **A cycle** — question A's visibility depends on question B, whose visibility depends on
  question A. Even a same-page pair creates an unrenderable state. This is a graph check the
  importer needs regardless of whether the condition syntax is a string or a structured mapping —
  it is orthogonal to §2's fork.
- **An option `value` that no such question has** — `when: {question: employer_pays, equals: "meybe"}`
  where `employer_pays`'s options are `yes`/`no`. Because `value` is typed (`int | str`,
  `freedom_ls/form_engine/schema.py:96`) the importer can compare the condition's literal against
  the *actual* set of `option.value`s on the referenced question and reject an unmatched literal
  outright, rather than silently producing a condition that can never be true.
- **A type mismatch** — comparing a `checkboxes` question's answer with an equality-style
  condition. SurveyJS's own docs draw this exact line: equality (`=`) is for single-value answers,
  `contains` is required for array-valued (checkbox) answers (§1) — the importer should reject
  (or require) the right comparison shape (e.g. `equals` only valid against `multiple_choice`,
  `short_text`/`long_text`, `number`; a checkboxes question requires an `includes`/`any_of`-style
  key instead) rather than silently comparing a list to a scalar and always evaluating false.
- **Condition on a question in a different form** — since a `key` is only unique *within* a form
  (mirroring XLSForm's `name`, which is unique within one form, not globally), a condition must
  resolve its `question:` reference against questions in the *same* `Form`; the importer already
  has that scope (a `FormPage` belongs to exactly one `Form`) and should reject a reference that
  cannot resolve within it with an error naming the form and the unresolved key.

All six of the above are checks on *meaning*, which — per §2 — a structured mapping lets Pydantic
and a small post-parse pass state as "this named field is wrong" rather than "somewhere in this
string is wrong."

---

## 5. Safe evaluation in Python (needed only if an expression string is chosen)

If FLS ever adopts an expression-string condition (`when: employer_pays == "yes"`), the general
problem of safely running an author-supplied expression in Python is well documented as **not
safely solvable by restricting the built-in `eval` function**: even sandboxes that strip
`__builtins__` can be walked around via Python's own introspection (subclass chains, `__import__`,
encoded strings) — "Python used to have an `rexec` module which tried to do something similar …
abandoned as being too complex and unworkable."
[Escaping Python Sandboxes](https://moshekaplan.com/posts/2012-10-26-escaping-python-sandboxes/),
[HackTricks — Bypass Python
sandboxes](https://hacktricks.wiki/en/generic-methodologies-and-resources/python/bypass-python-sandboxes/index.html).
The realistic options, surveyed for licence/maturity on PyPI directly:

| Library | What it is | Licence | Latest / status (checked on PyPI, Sept 2026) |
|---|---|---|---|
| [`simpleeval`](https://pypi.org/project/simpleeval/) | Restricted-grammar arithmetic/boolean expression evaluator over Python's own operator syntax, with an explicit builtin-function denylist and blocked `_`/`func_`-prefixed attribute access | MIT | v1.0.8; "5 - Production/Stable". Its own docs are explicit that "the sandboxing / safety features … only apply to the expression that is passed in" — the embedding application must not itself hand it unsafe objects. |
| [`asteval`](https://pypi.org/project/asteval/) | Walks Python's own `ast` module rather than executing it, "a pretty complete subset of the Python language," disallows `eval`/`exec`/`yield`/`async`/class creation/dunder access, no imports by default | MIT | v1.0.10; "5 - Production/Stable" |
| Hand-written parser over a tiny grammar (`pyparsing` or `lark`) | Author defines the entire grammar; nothing outside it can be expressed, by construction — the strongest safety property because there is no general-purpose language underneath to escape from | Both MIT | `pyparsing` v3.3.2, "5 - Production/Stable" ([PyPI](https://pypi.org/project/pyparsing/)); `lark` v1.3.1, "5 - Production/Stable" ([PyPI](https://pypi.org/project/lark/)) |
| `json-logic-py` (a JsonLogic interpreter for Python) | Evaluates the JsonLogic structured-data format (§1) — no string parsing at all, since the "expression" is already a JSON/YAML tree | MIT | `pip install json-logic`; GitHub shows 226 stars / 91 forks / 22 commits / 15 open issues — real but modest, unhurried maintenance. [nadirizr/json-logic-py](https://github.com/nadirizr/json-logic-py) |
| [`cel-python`](https://pypi.org/project/cel-python/) | Pure-Python implementation of Google's CEL (§1) | Apache 2.0 | v0.5.0 (Jan 2026); "4 - Beta", 3 listed maintainers, regular release cadence through 2025–2026 |

Whichever of these is chosen, the non-negotiable property is the one CEL and JsonLogic get for
free by construction and `simpleeval`/`asteval` have to defend by continuous denylisting: **no
evaluation path from an author-supplied condition may reach a Python builtin, an attribute lookup
that reaches outside the data dict handed to it, or an import.** A hand-rolled grammar (`pyparsing`/
`lark`) or a structured-data interpreter (JsonLogic) gets this by having no general-purpose
execution semantics underneath at all; `simpleeval`/`asteval` get it by an ongoing denylist that
has to be trusted to stay ahead of new bypasses — which is a maintenance liability, not a one-time
cost.

**This entire section is moot if §2/§7 recommend structured data**: a structured mapping
interpreted by a few lines of first-party Python (a plain `if`/`elif` over known keys, comparing a
condition's `equals` value against the learner's recorded answer) has no general expression
evaluator in it at all, and therefore none of this survey's sandbox-escape history applies to it.

---

## 6. Backward compatibility

Every existing `FormQuestion` in every existing form file — including both pages of
`demo_content/functionality_demo_application_form` — has no condition key today. Whatever is added
must be optional, default to "always visible" (i.e. absent means no change in behaviour), and
require no rewrite of a single existing file. FLS's own schema already establishes the pattern for
this: `Form.quiz_show_incorrect` and `Form.quiz_pass_percentage` are `X | None = Field(None, ...)`
with a `model_validator` enforcing the *cross-field* rule (required together, forbidden together)
rather than baking that rule into the field's own type
(`freedom_ls/form_engine/schema.py:40-77`). A `when: FormQuestionCondition | None = Field(None,
...)` field on `FormQuestion` (and the accompanying `key: str | None = Field(None, ...)` needed to
make `when` referenceable at all, §3) follows the same convention exactly, and — because every
model in `content_base`/`form_engine` uses `ConfigDict(extra="forbid")`
(`freedom_ls/content_base/schema.py:23`) — adding either field is additive and cannot silently
mis-parse an existing file's frontmatter the way a looser schema might. Nothing else in this survey
bears specifically on this point beyond confirming, across every system studied, that the
condition/branch feature is *always* an optional addition layered onto an existing question model,
never a restructuring of it — XLSForm's `relevant` column, SurveyJS's `visibleIf`, JSON Schema's
`if`, and Home Assistant's `condition` blocks are all absent-by-default properties on an
already-complete item definition, not a redesign of the item.

---

## 7. What this suggests for FLS

Three candidate syntaxes, written out against the real
`demo_content/functionality_demo_application_form` employer-pays case. All three assume a new,
optional, author-chosen `key: str | None` field on `FormQuestion` (§3) — without it, none of these
can name `employer_pays` at all, only its unreadable `uuid`.

### Candidate A — expression string (XLSForm/SurveyJS-style)

```yaml
# 1. about-you.yaml — new question
---
question: Will your employer pay for this course?
type: multiple_choice
required: true
key: employer_pays
options:
- text: "Yes"
  value: "yes"
- text: "No"
  value: "no"
---
question: What is your employer's name?
type: short_text
required: true
key: employer_name
when: "employer_pays == 'yes'"
```

- *Validation story*: Pydantic can only type `when` as `str | None`; every check in §4 (dangling
  reference, forward reference, cycle, bad option value, type mismatch) needs a second-pass
  expression parser before it can even be attempted, and any error message has to point into a
  parsed offset inside a one-line string rather than at a named field.
- *Cost*: needs a real evaluator (§5) with an ongoing "no builtins reachable" obligation; reads
  compactly for the simple case but the ergonomics/escaping problems GitHub Actions still has
  today (§1, §2) are the concrete downside of choosing this path.

### Candidate B — structured mapping, single condition (Home-Assistant-flavoured)

```yaml
---
question: What is your employer's name?
type: short_text
required: true
key: employer_name
when:
  question: employer_pays
  equals: "yes"
```

- *Validation story*: `when` becomes a small nested Pydantic model (`question: str`,
  `equals: str | int`), so every §4 check is a named-field check: "the `question` field of `when`
  on page 1 names `employer_pay`, but no question in this form has `key: employer_pay`" is a
  message Pydantic/a `model_validator` can produce directly, in the same voice as
  `Form.validate_quiz_fields` already does.
- *Cost*: needs its own nested shape the moment a second condition or an `and`/`or` is wanted
  (Home Assistant's answer is a further nested `condition: and` block, §1) — more YAML for compound
  cases, and no smooth growth path to arithmetic the way an expression string has.

### Candidate C — structured mapping with a combinator envelope from day one

```yaml
---
question: What is your employer's name?
type: short_text
required: true
key: employer_name
when:
  all:
    - question: employer_pays
      equals: "yes"
```

- *Validation story*: identical to B, plus a place to grow `all`/`any` (mirroring Home Assistant's
  `and`/`or`) without a breaking schema change later.
- *Cost*: for the single-condition case (all of v1's stated use cases: employer-pays,
  survey branching) it is pure ceremony — a wrapping list for something that is never combined —
  which reads as premature generality for a feature explicitly scoped to "not quizzes" and a single
  named use case.

### Recommendation

**Candidate B.** It gives Pydantic real field types to validate against (§2's central argument),
lets every authoring-time error in §4 name the exact wrong field rather than an offset into a
string, requires no expression evaluator and therefore none of §5's sandbox-escape history applies,
and is what a future visual editor's own data model would look like anyway with no round-tripping
risk. It costs nothing when only "not quizzes" simple single-condition visibility is in scope, which
matches the brief precisely; it is not what to reach for if/when a future version needs boolean
combinators or arithmetic, at which point Candidate C's `all`/`any` envelope (or, if genuinely
warranted by real demand, an expression string as an additive alternative form of `when`) is the
natural next step — but building that combinator envelope now, with a single condition to hold, is
exactly the "don't build functionality that is not explicitly requested" case this project's own
conventions warn against.

**FLS-native naming, translated from the sources above**: the new stable identifier this feature
needs should be called `key` on `FormQuestion` (playing the role XLSForm calls `name` and Qualtrics
splits out as the export tag against its `QID`) — `key` was chosen here, not `name`, because FLS
content models already reserve `title`/`subtitle` for display copy and QuestionOption/other models
have no precedent for a bare `name` field; this is noted as a naming choice for the next design
stage to confirm against `.claude/sdd/config.md`'s vocabulary sources, not a decision this research
document is authorised to finalise.

---

status: ok
reason: research complete; QTI worked XML example (rtest13.xml) could not be independently retrieved (404 on the historical mirror checked) — reported at spec-text level only, noted inline in §1
