# Conditional pages and questions

Let a form author gate a `FormPage`, a `FormQuestion` or a `FormContent` block on an answer the
learner has already given, so a sitting only ever shows the questions that apply to that learner.

The case that drives this: an application form asks whether the learner's employer is paying for the
course. An applicant who says yes gets a page of employer questions, company name, billing contact,
purchase order. An applicant who says no never sees that page and is never held up by its required
questions.

Today every sitting of a `Form` sees every `FormPage` and every `FormQuestion` on it, in the authored
order, and a required question anywhere in the form blocks submission whether or not it was ever
relevant to that learner.

## What a condition gates

A **condition** is a rule attached to the thing it controls. "Show me when question X was answered
Y". A `FormPage`, a `FormQuestion` and a `FormContent` block can each carry one. When the condition
is false the thing is not rendered, not saved to, and not counted as outstanding.

A page whose condition is false is skipped. That is the whole of routing. There is no separate
jump-to-page mechanism, because "skip this page unless the employer is paying" already expresses
every branch this feature is for. A routing graph would add a second way to say the same thing, and
with it an author error that gating cannot produce: two rules sending one learner to two places.
`research_conditional_logic_models.md` covers how Qualtrics ended up maintaining three mechanisms at
three granularities, display, skip and branch logic, and what that cost.

## The earlier-page rule

**A condition's source question must sit on an earlier `FormPage` than the thing it controls.** The
importer rejects anything else.

This is the decision everything else rests on. FLS's two runners are server-rendered and
POST-per-page, the course player's `form_fill_page` and the application shell's
`application_form_page`. A condition whose source was answered on an earlier page can be evaluated
on the server from `FormProgress.answers` alone, at the moment the page is rendered and again at the
moment it is submitted. There is one evaluator, it is the one that already gates storage and
required-validation, and it cannot disagree with itself. The learner gets a correct path with
JavaScript switched off.

Same-page reveal is what the rule buys out. An author who wants a follow-up question conditional on
an answer puts the trigger question on its own page, which is GOV.UK's default structure for any
form rather than a fallback, and which their own component guidance recommends outright for a
follow-up of more than one field. The cost is real and it lands on surveys. "Other, please specify"
now needs a page break, which reads as clumsy. That is the price of having no client-side rule
interpreter to keep in lock-step with the Python one, and it is worth paying while the feature is
this young.

`research_evaluation_architecture.md` sets out the three postures and what a duplicated rule engine
costs. `research_branching_ux_and_accessibility.md` carries GOV.UK's own findings on conditionally
revealed questions, including the accessibility problems they could not solve by adding more ARIA.

## How a condition is authored

Forms are authored as files, a directory holding `form.md` and one YAML file per page, so a
condition is a key in that YAML, validated by the Pydantic schemas in `form_engine/schema.py` at
import.

Two things are new.

**A `FormQuestion` needs a stable handle an author can type.** Every content document already
carries a `uuid`, but tooling writes those on first save and a condition reading
`uuid: 0a73990c-d232-4da1-91ba-84ed30c683b9` is unmaintainable. `Form` and `FormPage` both inherit a
`slug` from `TitledContent`. `FormQuestion` extends `BaseContent` and has none. Give it one,
author-chosen, unique within its form. This is the same concept `slug` already names, a stable and
readable identifier for a piece of content, so it needs no new word. A `FormQuestion` never appears
in a URL, so nothing else has to change to accommodate it.

**A condition is structured data, not an expression string**:

```yaml
question: What is your employer's name?
type: short_text
required: true
slug: employer_name
when:
  question: employer_pays
  equals: "yes"
```

Each part is its own typed Pydantic field, so an import error can say which key is wrong rather than
pointing at an offset inside a string. That is the voice `Form.validate_quiz_fields` already uses
when it quotes `file_path`. There is no expression evaluator, so none of the Python sandbox-escape
history applies. A checkbox source needs a membership test rather than equality, since its answer is
a set.

`when` stays absent by default. Every form file that exists today keeps working untouched.

The importer rejects a dangling question reference, a source on the same page or later, a cycle, and
a literal that matches no `QuestionOption.value` on the referenced question. That last one matters
because a typo'd value otherwise produces a condition that is silently never true.
`research_authoring_syntax.md` compares the candidate syntaxes against the real
`demo_content/functionality_demo_application_form` files and surveys what each system does when a
referenced name is renamed or duplicated.

## What happens to answers that fall off the path

An applicant says the employer is paying, answers five employer questions, then changes their mind.

**The five `QuestionAnswer` rows survive while the sitting is in progress and are deleted when it is
submitted.** Flip-flopping costs the applicant nothing, since the answers are still there if they
switch back, and a completed sitting holds no answer to a question it never really asked. Every
reader in between filters by the live path, so an off-path row never reaches the check-your-answers
page, the answered tally or a score.

Deleting the moment the condition goes false is simpler to reason about, but it makes an applicant
retype employer details because they changed their mind twice.
`research_answer_lifecycle_and_reporting.md` has what each choice cost the systems that made it, and
why coupling "hidden" to "value discarded" is what turned simple condition chains into a correctness
hazard for Gravity Forms.

Two rules follow from this.

- **`save_answers` must be given the questions the path says apply, never every question on the
  page.** A value can reach the POST body for a question the learner cannot see, through browser
  autofill, or from a value typed before they switched the trigger answer. Nothing but the server's
  own evaluation decides what gets stored.
- **`unanswered_required_on_page` and `unanswered_required_in_form` recompute the reachable set
  server-side every time.** A required question that is off-path must not block submission. A
  client-supplied "this one was hidden" flag would be a way to skip mandatory questions. This is the
  same reasoning those two functions already apply, and they have never trusted what a page rendered.

## Scoring

`max_score` becomes a property of the sitting, not of the form. A `CATEGORY_VALUE_SUM` survey counts
only the questions this sitting's path actually reached, and a `FormPage.category` subtree that was
entirely inapplicable drops out of that sitting's `scores` tree rather than contributing points the
learner was never eligible to earn.

Without this, a self-funded applicant is marked down against a denominator that includes employer
questions they could not have answered, and two learners in one cohort stop being comparable.
`freedom_ls/reports/` reads `scores["max_score"]` per attempt and divides by it, so it has to present
"out of N" per learner rather than once per column.

**Conditions are rejected on a `QUIZ` form.** Quizzes are out of scope by intent, and excluding them
at import keeps `compute_quiz_scores`, `quiz_percentage`, `passed` and `quiz_verdict` untouched. It
also keeps this feature clear of the question bank and per-attempt draw that
`spec_dd/2. in progress/compliance-form-randomization` is designing.

## The path a sitting took

A sitting persists a record of the pages and questions it was actually asked.

Reachability could be recomputed from the answers whenever it is needed, but then an author editing a
condition after the fact silently rewrites what the records say an applicant was asked, and a report
can disagree with the check-your-answers page the applicant actually saw. FLS already takes the
opposite position where it matters. `compute_quiz_scores` documents that scores are frozen at
submission and never rescored, and `reports/gather.py` insists on frozen batched reads rather than
live recomputation.

`spec_dd/2. in progress/compliance-form-randomization` wants a per-attempt record of the realised
order and subset a learner saw, for the same audit reasons. These are one concept, what this sitting
was actually shown, and whichever spec lands first should design the record so the other can use it.

## What changes for the learner

The runner surfaces all assume today that every sitting sees every page, and each needs revisiting.

- **`resume_page_number` and `furthest_page_reached`.** A monotonic page number cannot distinguish
  "page 4 was skipped" from "page 4 has not been reached yet". A resume must not drop a learner onto
  a page their answers say does not apply to them.
- **`build_page_links`.** A page that no longer applies leaves the page-jump nav entirely. It is not
  shown greyed out. The existing `is_accessible` treatment is for pages ahead of where the learner
  has got to, which is a different thing, and a locked-looking link the learner can never reach is
  the pattern GOV.UK's multi-step guidance argues against.
- **`answered_counts`.** `total_question_count` counts every `FormQuestion` in the form. Once
  questions can be skipped it is a denominator the form cannot keep, and the progress indicator
  understates what the learner has actually finished.
- **`question_number()`.** It keeps meaning what it means now, a stable ordinal in the full authored
  form, because the `data-testid` attributes and the "Question 5 needs an answer" message need an
  identity that does not shift with the path taken. Anything the learner reads as a position is a
  separate, path-derived value.
- **The check-your-answers page.** Editing an answer that changes which questions apply routes the
  applicant through the newly applicable ones before returning them to the review, rather than
  landing them straight back on it with a section they have never filled in. The existing
  `return=check` marker sends an edit straight back and will not do this on its own.

Nothing auto-advances or auto-submits because a radio changed. Continue stays a deliberate action.

## Out of scope

- **Quizzes**, per above.
- **Same-page reveal**, in any form. No HTMX partial, no Alpine rule interpreter. Relaxing the
  earlier-page rule later does not disturb anything decided here.
- **A visible-but-disabled question.** The idea's original "show or unlock" turns out to be one
  behaviour, not two. A question that does not apply is not rendered. A disabled control is not
  focusable, is often not announced at all, is exempt from the contrast rules a live control must
  meet, and, per GOV.UK's guidance for exactly this multi-step-form case, leaves people unsure
  whether they are allowed to change it.
- **Boolean combinators.** One condition per target, which covers the employer case and every survey
  case named so far. `all`/`any` is an additive change to the same `when` key when something real
  needs it.
- **Conditions referencing another form**, or anything outside the sitting's own answers.

## Terminology

| Term | Status | Meaning / source |
| --- | --- | --- |
| `condition` | coined | The rule gating a `FormPage`, `FormQuestion` or `FormContent`. Django's `UniqueConstraint(condition=...)` is the ORM's own word in another layer, and nothing in the FLS domain held this one. |
| path | coined | The pages and questions a given sitting was actually asked. Do not name a field `path`, because `BaseContent.file_path` and `calculate_path_from_root` already mean a file location. |

## Research

- `research_conditional_logic_models.md`. How twelve systems model a condition: rule shape, operators,
  reference scope, cycles, and authoring-time validation.
- `research_evaluation_architecture.md`. Server vs client vs both, what a duplicated rule engine costs,
  HTMX reveal patterns, and what Alpine's CSP build forbids.
- `research_branching_ux_and_accessibility.md`. GOV.UK's conditional-reveal findings, the WCAG criteria
  in play, `display:none` vs `disabled` vs `aria-hidden`, and progress indicators with no reliable total.
- `research_answer_lifecycle_and_reporting.md`. Orphaned answers, "not asked" vs "asked and skipped",
  the hidden-required deadlock, and prorated vs fixed denominators.
- `research_authoring_syntax.md`. Expression string vs structured data, how other systems name a
  referenceable field, and the checks an importer should make.
