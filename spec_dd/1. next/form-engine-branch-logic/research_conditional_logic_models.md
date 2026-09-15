# Research: how comparable systems model a condition

Scope: the **data model and semantics** of conditional visibility/branching in other survey, form and
assessment systems — not their authoring UI and not their authoring syntax (sibling research notes
cover those). Grounded against FLS's `freedom_ls/form_engine` models: `Form` (`strategy` one of
`CATEGORY_VALUE_SUM`, `QUIZ`, `UNSCORED`), `FormPage` (ordered, optional `category`), `FormContent`
(markdown block, ordered), `FormQuestion` (ordered, `type`, `required`, optional `category`),
`QuestionOption` (`text`, `value`, `order`, `correct`), and the runtime `FormProgress`/`QuestionAnswer`
pair. Two runners consume a form one page per POST: `learner_interface/views.py::form_fill_page` and
`course_applications/views.py`; `form_engine/paging.py` holds the shared page arithmetic (resume page,
page-jump nav, unanswered-required checks).

---

## 1. The rule shape

Three genuinely different shapes recur across the field: a rule **attached to the target** ("show me
when…"), a rule **attached to the source** ("when I am answered, reveal…"), and a **separate routing
table** that references both ends without living on either.

**Rule-on-target** is the shape used by every system built around a general boolean-expression
property on the controlled element:

- **SurveyJS**: `visibleIf`, `enableIf` and `requiredIf` are properties of the question (or panel/page)
  they control; setting one on a panel or page cascades it to every nested question. [SurveyJS conditional logic](https://surveyjs.io/form-library/documentation/design-survey/conditional-logic)
- **XLSForm/ODK**: the `relevant` column lives on the row (question) it controls, holding an XPath
  boolean expression. [ODK XLSForm](https://docs.getodk.org/xlsform/), [ODK Form Logic](https://docs.getodk.org/form-logic/)
- **Qualtrics Display Logic**: attached per-question (or even per answer-choice) from the question
  editor, not from the source question. [Qualtrics Display Logic](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/display-logic/)
- **Gravity Forms / WPForms**: "conditional logic" is configured on the field to be shown/hidden,
  picking which other field and value it depends on. [Gravity Forms: Enabling Conditional Logic](https://docs.gravityforms.com/enable-conditional-logic/), [WPForms conditional logic](https://wpforms.com/docs/how-to-use-and-or-conditional-logic/)
- **IMS QTI**: `preCondition` is a child of the `assessmentItem`/`assessmentSection` it gates — the
  target owns the rule. [IMS QTI v2.1 Implementation Guide](https://www.imsglobal.org/question/qtiv2p1/imsqti_implv2p1.html)

**Rule-on-source** is the shape used by systems whose unit of authoring is "what happens after this
question/page is answered":

- **Google Forms**: "Go to section based on answer" is configured at the bottom of the *source*
  section, one target section per option, only for multiple-choice/dropdown questions. [Google support: show questions based on answers](https://support.google.com/docs/answer/141062?hl=en)
- **Typeform Logic Jumps**: a jump is "Execute the jump if [condition on this question] → go to
  [target question]" — authored against the source question, forward-only. [Typeform Logic Jumps](https://www.typeform.com/developers/create/logic-jumps/)
- **SurveyMonkey Question Skip Logic**: configured on the question, "skip respondents to a later page…
  based on their answer." Page Skip Logic is a companion rule attached to the *page* rather than a
  question: it fires unconditionally for everyone who reaches that page, no condition at all. Question
  logic overrides page logic when both apply. [SurveyMonkey Question Skip Logic](https://help.surveymonkey.com/en/surveymonkey/create/question-skip-logic/), [SurveyMonkey Page Skip Logic](https://help.surveymonkey.com/en/surveymonkey/create/page-skip-logic/)
- **Qualtrics Skip Logic**: also source-attached, "sends respondents forward to a later part of the
  survey based on their answer," restricted to jumping within the same block. [Qualtrics Skip Logic](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/skip-logic/)
- **Moodle Lesson module Jumps**: each *answer* on a Lesson content/question page carries its own Jump
  target (a specific page, "Next page", "End of lesson", etc.) — the most granular rule-on-source shape,
  one rule per option rather than per question. [Moodle Lesson module](https://docs.moodle.org/500/en/Lesson_module)
- **GOV.UK Forms** (the current UK government forms product): "Add a route to a question where people
  select only one option from a list… they'll be skipped forward to a later question, the end of the
  form, or an exit page." A second route can be added for "any other answer," giving two branches from
  one source question. Routing sources are restricted to single-select questions. [GOV.UK Forms features](https://www.forms.service.gov.uk/about/features)

**Separate routing table** is the shape used where the unit of branching is not a question at all but
a block/section of the survey flow, or where conditions are reusable named objects independent of any
one page:

- **Qualtrics Branch Logic**: lives in the Survey Flow editor, not on any question or block. A branch
  element wraps other Survey Flow elements (including nested branches) and its condition can reference
  "earlier survey responses… embedded data… system variables." [Qualtrics Branch Logic](https://www.qualtrics.com/support/survey-platform/survey-module/survey-flow/standard-elements/branch-logic/), [Qualtrics Survey Flow overview](https://www.qualtrics.com/support/survey-platform/survey-module/survey-flow/survey-flow-overview/)
- **IMS QTI `branchRule`**: syntactically a sibling of `preCondition` (also a child of the item/section)
  but semantically a routing statement — "sets an alternative target as the next item or section" — so
  it straddles rule-on-target-as-container and routing-table.

**Why Qualtrics ended up with three separate mechanisms.** Qualtrics's own documentation frames these
as answering three different questions at three different granularities: Display Logic answers "should
this one question (or choice) be shown at all?", evaluated purely against data already available about
the respondent; Skip Logic answers "which question should this respondent see next, within this
block?"; Branch Logic answers "which whole block/section of the survey should this respondent go
through?" [Qualtrics: Using Logic](https://www.qualtrics.com/support/survey-platform/survey-module/using-logic/). Each
operates at a different level of the survey's structural hierarchy (choice/question, question, block),
and each has different navigational side effects (none, forward-skip-within-block,
whole-block-routing-with-back-button changes) — collapsing them into one mechanism would mean either
losing the finer-grained choice-level hiding that Display Logic gives, or losing the section-level
reordering that Branch Logic gives from something meant to hide a single field. The trade-off Qualtrics
made is more surface area and more moving parts (author confusion about which one to reach for) in
exchange for each mechanism staying simple and matching its own scope exactly.

---

## 2. Condition expressions

**Operators.** Nearly every system in this list offers the same small core — equals/not-equals,
contains/any-of for multi-select, is-answered/is-blank, and numeric comparison — with the differences
mostly in naming and in how far past that core a system goes:

- **SurveyJS** is the widest: `equal`/`notequal`, `<`/`>`/`<=`/`>=`, `contains`/`*=`, `anyof`, `allof`,
  `noneof`, `empty`/`notempty`, plus a `!`/`negate` unary. [SurveyJS conditional logic](https://surveyjs.io/form-library/documentation/design-survey/conditional-logic)
- **WPForms**: is / is not / empty / not empty / contains / does not contain / starts with / ends with
  / greater than / less than. [WPForms conditional logic](https://wpforms.com/docs/how-to-use-and-or-conditional-logic/)
- **REDCap branching logic**: `=`, `<`, `>`, `<=`, `>=`, `<>`, combined with `and`/`or`; for a checkbox
  field, each option is tested individually with a positional syntax, e.g. `[checklist(1)] = 1` for "was
  option 1 checked." Quoting rules differ by field type: string/coded values need quotes, numeric
  text-validated fields being compared with `<`/`>` do not. [REDCap Branching Logic (QMUL docs)](https://docs.redcap.qmul.ac.uk/adding-data/branching-logic/)
- **XLSForm/ODK `relevant`**: a full XPath boolean expression, so it inherits XPath's operators
  (`=`, `<=`, `>`, `and`, `or`, `not()`) plus purpose-built functions: `selected(${field}, 'value')` for
  "was this option chosen" on a multi-select, `count-selected()`, `contains()`, `starts-with()`,
  `regex()`. [ODK Form Logic](https://docs.getodk.org/form-logic/)
- **Qualtrics**: choices are described more abstractly in the UI ("chose a specific answer," "did not
  choose," "text response contains") layered on top of the same True/False "logic sets" combined with
  AND/OR; the public docs do not name a single canonical operator list the way REDCap or SurveyJS does. [Qualtrics Display Logic](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/display-logic/)

**Multi-select matching.** The recurring answer is "does the selected set contain this value/option,"
never "does the selected set equal exactly this set" — ODK's `selected()` tests membership, SurveyJS's
`anyof`/`allof`/`noneof` test membership variants (any, all, none of a list present), and REDCap's
`[checklist(n)] = 1` tests one checkbox position at a time rather than the whole set atomically. No
system surveyed exposes a raw "selected options equals exactly {A, B}" operator as a first-class
primitive — a checkbox condition is built from one-or-more single-option membership tests ANDed/ORed
together.

**AND/OR groups and nesting.** Nearly universal, with two different limits on depth:

- **Flat, two-level** is common: a list of conditions, each ANDed or all ORed as a single group, with no
  further nesting — this is how Gravity Forms and WPForms present "Show/Hide if [All/Any] of the
  following match," and it is what most authors mean by "conditions." [Gravity Forms: Enabling Conditional Logic](https://docs.gravityforms.com/enable-conditional-logic/)
- **Arbitrarily nested** is offered by systems whose expression is a real parenthesised grammar:
  REDCap explicitly allows "many parenthetical levels" of nesting [REDCap Branching Logic (QMUL docs)](https://docs.redcap.qmul.ac.uk/adding-data/branching-logic/); Typeform's Logic Jumps support AND/OR
  combined in one jump [Typeform Logic Jumps](https://www.typeform.com/developers/create/logic-jumps/); XLSForm's
  `relevant` inherits XPath's full expression grammar including arbitrary parenthesised boolean
  composition. [ODK Form Logic](https://docs.getodk.org/form-logic/)

**General expression languages, and sandboxing.** Three systems hand the author a real expression
language rather than a fixed condition-builder UI:

- **ODK/XLSForm**: raw XPath 1.0, evaluated against the XForm's instance data by the client engine
  (JavaRosa/Enketo). The sandbox is structural, not linguistic: expressions can only read the model's
  own instance nodes, there is no host/network/eval access, and the function library is the fixed
  XPath+ODK extension set (no arbitrary code). [ODK Form Logic](https://docs.getodk.org/form-logic/)
- **SurveyJS**: its own small expression language (`{questionName}` interpolation, the operator table
  in §2, boolean composition), parsed and evaluated by the library's own `ExpressionRunner` — not
  JavaScript `eval`. The library exposes a `validateExpressions()` call that reports unknown variables,
  unknown functions and syntax errors before the expression is trusted. [SurveyJS: Adding Expressions](https://surveyjs.io/form-library/documentation/api-reference/expression-model)
- **IMS QTI**: its own XML-based expression grammar (`variable`, `baseValue`, `match`, `and`/`or`/`not`,
  etc.) rather than a scripting language — deliberately not Turing-complete, which is what lets a QTI
  engine statically resolve every `preCondition`/`branchRule` without running arbitrary code. [IMS QTI v2.1 Implementation Guide](https://www.imsglobal.org/question/qtiv2p1/imsqti_implv2p1.html)

No system surveyed hands the author a general-purpose scripting language (JavaScript, Python) sandboxed
at runtime; every one of them instead defines its own small, closed expression grammar (or, for
condition-builder UIs like Qualtrics/Gravity Forms/WPForms, no expression syntax at all — just
structured dropdowns that assemble the same handful of operators). That closed-grammar choice is itself
the sandboxing strategy: there is no `eval` to escape because there is no general-purpose language to
begin with.

---

## 3. Scope of reference

The most consequential split in the survey is not about operators — it is about **whether a
condition's evaluation model is "the whole document exists at once" or "the document is revealed one
page at a time."**

**Whole-document-at-once systems** hold every field's live value in one in-memory model on the client
(or evaluate a full instance tree in one pass), so a condition can reference *any* field regardless of
its position in the document — the only real risk is a field that has no value yet (typically treated
as blank/undefined, which most comparison operators simply evaluate as false):

- **SurveyJS** re-evaluates every `visibleIf`/`enableIf` "whenever referenced values change," and its
  docs describe no restriction to earlier questions — the model is a single live object graph. [SurveyJS conditional logic](https://surveyjs.io/form-library/documentation/design-survey/conditional-logic)
- **ODK/XForms**: `relevant` (and `calculate`) expressions can address any node in the XForm's instance
  document by XPath, forward or backward; the engine (JavaRosa) builds a dependency graph over the whole
  instance and re-evaluates whatever depends on a changed node, rather than walking the form
  top-to-bottom once. [ODK Form Logic](https://docs.getodk.org/form-logic/)
- **Qualtrics Display Logic**, notably, is documented as technically able to reference a question the
  respondent has not yet seen — the platform's own linting (ExpertReview) *flags* this rather than
  rejecting it outright, which only makes sense if the underlying evaluation model permits it. [Qualtrics Display Logic](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/display-logic/)

**Page-per-submission systems**, by contrast, structurally *cannot* reference a later page's answer,
because that answer does not exist in the server's data yet when the condition needs evaluating — the
restriction is not a stylistic choice, it falls directly out of the architecture:

- **GOV.UK Forms**: routes always point "forward to a later question" — never backward, and never to
  something not yet reached, because a route is resolved as the respondent leaves the source question's
  page. [GOV.UK Forms features](https://www.forms.service.gov.uk/about/features)
- **Google Forms**: "go to section based on answer" is chosen when the respondent finishes the current
  section and clicks Next — by construction it can only route to a section not yet visited, never
  reference one already passed for its answer. [Google support](https://support.google.com/docs/answer/141062?hl=en)
- **Typeform**: "Logic jumps won't work if you're moving the respondent backwards in the form" is an
  explicit, named restriction — evaluation happens as the respondent leaves a question, so the jump
  target must lie ahead. [Typeform Logic Jumps](https://www.typeform.com/developers/create/logic-jumps/)
- **Qualtrics Skip Logic** is scoped even tighter — "respondents can only be skipped forward to
  questions within the same block" — a restriction one level narrower than "later in the survey." [Qualtrics Skip Logic](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/skip-logic/)
- **IMS QTI**: `branchRule`/`preCondition` are meaningful only in *linear* navigation mode, where items
  are visited in a fixed, one-way sequence — both are explicitly "ignored in nonlinear mode," where the
  candidate can revisit any item and a forward/backward distinction stops being well-defined. [IMS QTI v2.1 Implementation Guide](https://www.imsglobal.org/question/qtiv2p1/imsqti_implv2p1.html)

**Cross-form references.** None of the systems surveyed let a condition on one form reference an answer
recorded against a *different* form — REDCap is the partial exception in spirit (its branching logic
can reference any field in the same *project*, which may span multiple instruments/forms within that
project, because REDCap's unit of "the document" is the whole project's data dictionary rather than a
single form) but this is still one project's shared data model, not a genuine cross-form reference. [REDCap Branching Logic (QMUL docs)](https://docs.redcap.qmul.ac.uk/adding-data/branching-logic/)

**Why the earlier-pages-only restriction exists**, stated plainly: it is not a deliberate design
constraint chosen for its own sake in the page-per-submission systems above — it is a direct consequence
of *when* the condition is evaluated. A system that evaluates conditions against a live, fully-populated
in-memory document (SurveyJS, ODK/XForms, Qualtrics in-page Display Logic) can permit forward references
because "the value doesn't exist yet" degrades gracefully to "the value is blank" and the condition just
evaluates accordingly. A system that evaluates a condition once, at the moment of leaving a page, to
decide the *next* page to render (GOV.UK Forms, Google Forms, Typeform, Qualtrics Skip Logic, QTI in
linear mode) has no later answer to read at that moment — the page holding it has not been rendered yet
— so the restriction is structural, not a policy choice its authors could relax without also changing
how the runner works.

---

## 4. Chaining and cycles

**What happens when a revealed question is itself a condition source** — i.e. B is shown only when A
has a certain answer, and C is shown only when B has a certain answer — is handled with real variation:

- **Gravity Forms explicitly discourages this.** Its own documentation states plainly: "a field should
  not have conditional logic based on a field that also has conditional logic." The failure mode it
  documents is concrete: hiding a field resets its value, so a *dependent* condition then evaluates
  against that reset value rather than a true "unanswered" state, producing incorrect show/hide
  decisions further down the chain. Its prescribed fix is not "fix the chain," it's "don't chain" —
  flatten the dependency by adding every ancestor condition (A's condition *and* B's condition) directly
  onto C, instead of letting C depend transitively on B. [Gravity Forms: Nested Conditional Logic Limitations](https://docs.gravityforms.com/conditional-logic-limitations/)
- **ODK/XForms tolerates chains and detects true cycles.** Because `relevant`/`calculate` expressions
  are resolved via a dependency graph over the whole instance rather than a single top-to-bottom pass, a
  chain of dependent `relevant` expressions is not a special case at all — it is just more edges in the
  same graph, evaluated to a fixpoint. A genuine cycle (A depends on B, B depends on A) is rejected as a
  form-authoring error by the XForms toolchain rather than allowed to loop, though the ODK docs surveyed
  here describe this only at the level of "the specification prevents circular dependencies" without a
  worked pyxform error example. [ODK Form Logic](https://docs.getodk.org/form-logic/)
- **QTI sidesteps the problem structurally.** `branchRule`/`preCondition` only apply in linear
  navigation, where items are visited in one fixed, forward-only order — a branch rule's target can only
  be an item later in that same fixed sequence (or `EXIT_SECTION`), so there is no possibility of a
  cycle: the item ordering itself is acyclic by definition, and the mechanism is ignored altogether the
  moment navigation stops being strictly linear. [IMS QTI v2.1 Implementation Guide](https://www.imsglobal.org/question/qtiv2p1/imsqti_implv2p1.html)
- **Qualtrics Branch Logic tolerates nested branches by design** — "you can add multiple elements
  under the branch if desired," including other branches within branches — but this is nesting of
  *scope* (a branch inside a branch), not a dependency chain between conditions; it does not raise the
  same cycle risk because Branch Logic only ever moves forward through the Survey Flow. [Qualtrics Branch Logic](https://www.qualtrics.com/support/survey-platform/survey-module/survey-flow/standard-elements/branch-logic/)
- **REDCap and SurveyJS leave it to the author.** Neither's documentation surveyed here describes any
  automatic cycle detection or chain-depth limit; REDCap does state its expression grammar permits deep
  parenthetical nesting, which is nesting of a single condition's boolean structure, not a guard against
  a chain of dependent fields. [REDCap Branching Logic (QMUL docs)](https://docs.redcap.qmul.ac.uk/adding-data/branching-logic/), [SurveyJS conditional logic](https://surveyjs.io/form-library/documentation/design-survey/conditional-logic)

The pattern: systems whose evaluation model is a genuine dependency graph (ODK/XForms) can afford to
support chains because "evaluate to a fixpoint, reject true cycles" is a well-understood, decidable
problem on that graph. Systems whose evaluation model is "each field's visibility rule runs
independently against current form state, and hiding a field has a value-mutating side effect" (Gravity
Forms) run into trouble specifically *because* that side effect (clearing the value) interacts badly
with a downstream condition reading it — which is a warning that **coupling "hidden" to "value is
cleared" is what turns simple chaining into a correctness hazard**, not chaining itself.

---

## 5. Visibility vs enablement

Most systems surveyed offer only one state: shown or not shown. A few draw a second, distinct line
between "hidden" and "visible but not currently actionable":

- **SurveyJS is the clearest case of a genuine three-way split.** `visibleIf` removes an element
  entirely; `enableIf` keeps it visible but switches it to read-only when the expression is false;
  `requiredIf` independently toggles whether an otherwise-optional, visible field is currently mandatory.
  These are three orthogonal properties, not three values of one enum — a question can be visible,
  disabled, and required all at once, or visible, enabled, and optional. [SurveyJS conditional logic](https://surveyjs.io/form-library/documentation/design-survey/conditional-logic)
- **Moodle's "Restrict access" has an equivalent split, expressed as a per-condition toggle rather than
  a per-element property.** Every restriction carries an eye icon with two states: a closed eye hides
  the activity entirely from a student who doesn't meet it; an open eye leaves the activity's name
  visible in the course but greyed out, "with information about why they can't access it yet" — visible,
  named, but not clickable, i.e. exactly the visible-but-disabled state SurveyJS's `enableIf` produces.
  When several restrictions combine with AND, the *most* restrictive eye state wins (a single closed eye
  hides the whole combination until that condition clears, even if another condition in the same set has
  an open eye); OR/NOT-AND combinations collapse to a single shared eye icon rather than one per
  condition. It also has a secondary, separate effect on gradebook visibility. [Moodle Restrict access settings](https://docs.moodle.org/501/en/Restrict_access_settings)
- **What the visible-but-disabled state is used for**, in both cases, is *telling the person why*
  something isn't available yet, rather than making it look as though it never existed — Moodle's own
  wording is explicit that the point of the open-eye state is to show "information about why they can't
  access it yet." This is a UX property (surfacing the reason) sitting on top of a data-model property
  (still hidden from *interaction*, if not from *sight*).
  Whether that data-model property belongs in this research topic's scope or the sibling UX research
  is itself a judgement call — it is included here because it changes what "visible" means as a stored
  value, not only how it renders.
- **Nobody surveyed documents regretting having both states.** No source found states this in so many
  words. The closest evidence of a real cost from conflating the two rather than separating them is
  Gravity Forms' documented value-reset bug (§4): because Gravity Forms has only a single
  hidden/shown state, and hiding a field also clears its stored value as a side effect, an author who
  wants "keep the answer, just don't let them see or change it right now" has no first-class way to say
  that — they are pushed toward complex flatten-the-chain workarounds instead. That is closer to an
  implicit argument *for* a separate disabled state (to decouple "don't show/interact" from "discard the
  value") than a documented regret about having one.
- **Every other system surveyed — Google Forms, Typeform, SurveyMonkey, Qualtrics Display/Skip/Branch
  Logic, REDCap, ODK/XLSForm, Gravity Forms, WPForms, IMS QTI, GOV.UK Forms — offers only the single
  hidden/shown distinction**, with no documented "visible but disabled" state.

---

## 6. Validation at authoring time

What a system checks before it will let an author save or publish a rule varies from "nothing beyond a
UI that can't construct an invalid rule" to "a linter that flags smells without blocking save":

- **Qualtrics: a targeted linter (ExpertReview), not a hard save-time gate.** It surfaces "Invalid
  Logic" once a referenced question or choice is deleted out from under a rule, and separately flags
  display logic that references a question the respondent has not yet seen — but this is advisory
  tooling layered on top of survey editing, not something documented as blocking Save itself. [Qualtrics Display Logic](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/display-logic/)
- **ODK/XLSForm: compile-time rejection via pyxform/the XForms toolchain.** A form with a genuine
  circular dependency between `relevant`/`calculate` expressions fails to compile — this is described at
  the level of "the specification prevents circular dependencies" in the sources surveyed here, without
  a worked example of the exact pyxform error text. [ODK Form Logic](https://docs.getodk.org/form-logic/)
- **Gravity Forms: no save-time validation at all for the chaining hazard it documents** (§4/§5) — the
  fragile "field depends on a field that is itself conditional" pattern is not blocked; the vendor's own
  fix is a *browser console script* an author can run manually to go find nested dependencies after the
  fact, which is about as far from authoring-time validation as a documented workaround gets. [Gravity Forms: Nested Conditional Logic Limitations](https://docs.gravityforms.com/conditional-logic-limitations/)
- **SurveyJS: an explicit, callable check, but opt-in and general-purpose rather than form-specific.**
  `validateExpressions()` reports unknown variables, unknown functions, and syntax errors — a real
  authoring-time check — but nothing surveyed here suggests it is run automatically on every save, and
  it validates the *expression's grammar and references*, not survey-specific smells like "this
  condition can never be true" or "this option value no longer exists on the referenced question." [SurveyJS: Adding Expressions](https://surveyjs.io/form-library/documentation/api-reference/expression-model)
- **GOV.UK Forms / Google Forms / Typeform: validation is structural, enforced by the routing UI itself
  rather than by a separate check.** Because a route/jump/section-target is chosen from a dropdown of
  pages that actually exist ahead of the current one, a dangling reference or a backward reference is
  something the editor's own UI does not let an author construct in the first place, rather than
  something checked after the fact. [GOV.UK Forms features](https://www.forms.service.gov.uk/about/features)
- **Nothing surveyed here documents a check for "a condition that can never be true"** (e.g., a
  condition requiring two mutually exclusive answers from the same single-select question) — this class
  of authoring error appears to be left to the author, everywhere.

The overall shape: **UI-constrained systems (GOV.UK Forms, Google Forms, Typeform) get correctness "for
free"** by only ever offering valid targets in the first place; **expression-language systems (ODK,
SurveyJS) get correctness through an explicit compile/validate step** that catches syntax and reference
errors but not semantic ones; and **condition-attached-to-target systems with a loose UI (Gravity
Forms)** are the ones documented as shipping a real, named authoring hazard with no save-time guard at
all.

---

## What this suggests for FLS

Three model shapes fit `form_engine`'s existing nouns, each translating a different one of the
architectures above. None of them is a work plan — each is named in FLS's vocabulary with its cost and
its payoff.

**A — condition attached to the target (`FormQuestion.visible_when` / a `FormContent.visible_when`),
mirroring SurveyJS `visibleIf` and ODK's `relevant`.** Each `FormQuestion` (and, if content-block
hiding is wanted, each `FormContent`) carries its own condition: a source `FormQuestion` FK, an
operator, and a value to compare against that source's `QuestionOption.value`(s) or its
`QuestionAnswer.text_answer`. *Costs*: the target is polymorphic across `FormQuestion` and
`FormContent` (and `FormPage`, if page-level hiding is wanted too), which means either three parallel
condition tables or a generic-FK target — plus every reader of a page's children (`FormPage.children()`,
`paging.page_questions()`, the two runners' page-render code, `unanswered_required_on_page`) needs to
consult the condition before treating a `FormQuestion`/`FormContent` as "on this page" at all. *Buys*:
maps most directly onto the stated use case ("if yes, a set of employer questions appears") — each
employer question just names its own condition, no indirection to look up; and it is the shape every
comparison-operator author in this research already assumes an author is thinking in ("this question,
shown when…").

**B — condition attached to the source (`QuestionOption.reveals` or `FormQuestion.reveals_when`),
mirroring GOV.UK Forms' routes and Google Forms' "go to section based on answer."** The employer-pay
question itself declares what it unlocks per option — e.g. a through-table keyed on
`(QuestionOption, target FormQuestion)`, or a JSON map on the source `FormQuestion`. *Costs*: multiple
source questions targeting the same downstream question need an explicit combination rule (does any one
of them being satisfied reveal it, or must all be satisfied — the equivalent of REDCap's AND/OR groups),
which this shape has nowhere natural to hold unless it grows into shape C; and "why is this question
hidden" is now a query that has to search every other question's `reveals_when` rather than reading one
place. *Buys*: this shape lines up cleanly with how FLS's runner already works — a POST-per-page
architecture that (per §3 above) can only ever reveal something *later*, never something already
rendered, so a rule that lives on the source and is resolved the moment `FormProgress.save_answers()`
runs for that page fits the existing page-at-a-time evaluation point without inventing a new one; and it
keeps the common case (one employer-pay question driving several employer questions) to a single
authored place.

**C — a separate condition model, not living on either end, mirroring Qualtrics Branch Logic's Survey
Flow elements and REDCap's per-field logic strings as *reusable, named* objects.** A `FormCondition`
model (or similar) holds `form`, a source `FormQuestion`, an operator, a comparison value, and an
optional AND/OR group linking several `FormCondition` rows together; `FormQuestion`/`FormContent` rows
reference it by FK rather than embedding their own comparison inline. *Costs*: the most schema surface
of the three, and an extra join at read time for every page render; also raises the question of whether
conditions are named/reusable (several targets sharing one `FormCondition`, REDCap/DEFRA-style) or just
a normalised inline shape, which changes how much the extra table actually buys. *Buys*: it is the
natural home for authoring-time validation as a single pass — dangling references, forward references
to a later `FormPage.order`, and cycles between conditions can all be checked once, against one table,
the same way `schema.py`'s pydantic models already validate a form's YAML at import time — rather than
being scattered across whichever model ended up holding the condition in shapes A or B; and it is the
shape that scales cleanly if `CATEGORY_VALUE_SUM` surveys later want the same condition reused by
several unrelated questions.

Two structural findings from the comparison bear directly on all three shapes, regardless of which is
picked:

- **§3's earlier-pages-only restriction is not optional for FLS — it is what the runner already is.**
  FLS's two runners are server-rendered, POST-per-page, exactly the architecture that GOV.UK Forms,
  Google Forms, Typeform, and Qualtrics Skip Logic all sit in, and each of those systems states an
  earlier/later restriction that is a direct consequence of that architecture rather than a policy
  choice. Any condition here should reference a `FormQuestion` on a `FormPage` whose `order` is at or
  before the target's — a forward reference literally cannot be evaluated by the time the runner needs
  the answer, the way it structurally can in a single-page-of-live-JavaScript system like SurveyJS.
- **§4/§5's cross-cutting warning is that "hidden" must not silently mean "value discarded."** FLS
  already stores `QuestionAnswer` rows keyed uniquely per `(form_progress, question)`, independent of
  whether that question is currently shown; whichever shape is chosen, a `QuestionAnswer` behind a
  condition that later evaluates false should behave like ODK's dependency-graph re-evaluation (the
  value persists, unread, until the condition is true again) rather than Gravity Forms' documented
  reset-on-hide, which is exactly the behaviour Gravity Forms' own docs identify as the root cause of
  its chaining hazard.

---

status: ok
reason: All six research questions covered with concrete, cited detail from Google Forms, Typeform,
SurveyMonkey, Qualtrics (Display/Skip/Branch Logic), REDCap, Gravity Forms/WPForms, SurveyJS,
XLSForm/ODK, JSON Schema, IMS QTI, GOV.UK Forms, and Moodle (Lesson jumps and Restrict access). Closed
with three FLS-vocabulary model shapes and their trade-offs.
