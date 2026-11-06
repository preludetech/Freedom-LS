# Research: where the branch-logic condition is evaluated

Topic: for conditional visibility ("will your employer pay?" → reveal employer questions), where does
the system decide what is visible — server, client, or both? This is the architecture question the
user asked to be researched and given a recommendation on.

## 1. The three postures

**(a) Server-only, evaluated at page boundaries.** The rule runs once, server-side, at the point a page
is rendered or a page is submitted. A same-page reveal ("show the employer questions right under the
yes/no, on the same page") either does not exist as a feature, or costs a full round trip: submit the
page (or a partial), server recomputes which questions belong on it, re-renders.

- *Latency*: one extra request per reveal, ~50-300ms depending on infra, no client work.
- *Correctness*: trivially correct — there is exactly one implementation of the rule, and it is the one
  that also gates storage and validation, so "what's visible" and "what's allowed to be answered" can
  never disagree.
- *Code*: least code. One rule evaluator, one place it's called from (the page-render/page-submit path
  already in `form_engine/paging.py` and the view functions that use it).

**(b) Client-only reveal, server re-checks at submit.** JS holds its own notion of visibility (e.g. a
hidden `<div>` toggled by an Alpine/vanilla-JS handler reading the trigger field), and the server does
not compute visibility at all during page rendering — it only re-derives, at submission time, which
answers it will accept/require, by re-running (yet another, server-side) copy of the rule against the
posted data.

- *Latency*: zero round trip for the reveal itself — instant.
- *Correctness*: fragile. If the client's rule and the server's rule are not literally the same code,
  they can disagree, and the disagreement surfaces exactly when it's expensive: a learner sees a field,
  fills it in, and the server silently drops it because its own rule says the field was never eligible
  (or vice versa — the server demands an answer to a question the client never showed).
- *Code*: two rule implementations to maintain by hand, in two languages, with no structural link
  between them. This is the "two engines drift" problem named in (c) below, except here it's not even
  named as a risk to manage — it is simply two hand-written copies.

**(c) One rule, evaluated in both places.** The rule is data (JSON, or a small DSL), not code baked
into either side. Something interprets it server-side (Python) to compute visibility for rendering and
for validation; something interprets the *same* data client-side (JS) to compute visibility for instant
reveals. This is the shape form-building SaaS products converge on: Form.io's documentation describes
exactly this pattern — "the form schema operate[s] as infrastructure... rules are defined once in the
form schema, then executed consistently wherever the form runs, with the API server re-executing the
same rules on submission to prevent bypassing" ([Form.io — Form Conditional Logic and Validation That
Runs Everywhere](https://form.io/features/form-conditional-logic-form-validation/)).

- *Latency*: zero round trip for the reveal (client evaluates locally), server still authoritative at
  submit.
- *Correctness*: as good as (a) **if and only if** the two interpreters genuinely agree on every rule
  the data can express — which is a nontrivial property to hold, not a free consequence of "the data is
  shared."
- *Code*: most code of the three postures — a rule language has to be designed, a JSON/DSL schema
  versioned, *two* interpreters written and kept feature-equal, and (per the pattern above) the server
  interpreter has to re-run at submit regardless, because the client can't be trusted (see §2). The
  reveal is faster, but the validation work is not smaller than posture (a) — it's the exact same
  validation work, plus a second, client-side evaluator bolted on beside it.

**The specific failure mode of (c):** two implementations of one rule language drifting apart. Even
with a single shared JSON representation, "same JSON, two interpreters" only guarantees behavioural
parity if both interpreters implement precisely the same semantics — operator precedence, how missing
answers are treated, how multi-select comparisons work, floating point coercion, etc. A Python `if`
evaluator and a JS `eval`-avoiding evaluator (CSP forbids `eval`/`Function` — see §4) are two separate
programs that happen to read the same data; nothing stops one from being extended (a new operator, a
new comparison type) without the other following. Three concrete answers teams use to keep this from
silently rotting:

1. **Ship the rule JSON to the client and interpret it with a small, hand-written JS evaluator** that
   supports exactly the same operator set as the Python one, deliberately kept minimal so the surface
   for divergence stays small.
2. **Compile the server rule into a client predicate** (a code-generation step turns the stored rule
   into, e.g., a tiny generated JS function) rather than writing a second interpreter by hand — this
   trades "two engines" for "one engine plus one compiler," which fails loudly (a compile error) instead
   of silently (a semantic mismatch) when the rule grows a feature the compiler doesn't yet support.
3. **Contract tests that run the same rule fixtures through both interpreters** and assert identical
   output — a fixture list of (rule, answer-set) → expected-visible-set triples exercised against both
   the Python and the JS evaluator on every CI run, so drift is caught in the pipeline rather than in a
   support ticket about a field that "showed up but wouldn't save."

None of this is free. It is real design and ongoing maintenance cost purchased specifically for the
zero-round-trip reveal, and it is only worth it if the round trip actually matters to the user (see §6).

## 2. Server is always the authority

The client's opinion about what was visible can never be trusted for required-validation or for storing
answers, because a POST can carry anything: a learner (or anyone with a browser's dev tools, or `curl`)
can submit fields the UI never showed, omit fields the UI marked required, or submit values the reveal
logic was supposed to have prevented from ever being reachable. This is the same argument security
practice makes about client-side input validation generally, and it is well established:

> "Client-side validation is performed for usability purposes... [but] the application's security must
> not depend upon it... Authoritative validation checks must be enforced on the server side."
> — [OWASP Cornucopia — Frontend (FRE2)](https://cornucopia.owasp.org/edition/companion/FRE2/1.0/en)

> "From the server-side perspective... never trust what the client-side sends you. With some knowledge
> of browser inspect tools (or tools like curl) people can easily tweak what the browser sends you, go
> around client-side validations and even add unexpected fields to the request... Use client-side
> validation to help reduce the number of round trips to the server but do not rely on it for security."
> — [OWASP DevGuide, Input Validation](https://wangmj1.gitbooks.io/owasp-devguid/03-Build/0x06-InputValidation.html)

This is not a novel argument for FLS to make — it is the identical reasoning FLS already applies
elsewhere in the form engine: `unanswered_required_on_page` and `unanswered_required_in_form`
(`freedom_ls/form_engine/paging.py`) never trust that a page's *presented* fields match what's
*required* — they recompute the required set server-side from stored data and posted data, every time.
Branch logic sits on exactly the same fault line, one level up: "is this question required" already has
to be re-derived server-side per request; "is this question even eligible to exist for this sitting"
would need the identical treatment.

**The specific consequence for a rule engine:** the server has to be able to compute the visible set
*from stored answers alone* — not from anything the client asserts about what it showed. Concretely,
this means whatever evaluates "did the employer say yes" cannot take "the client says the employer
question was answered yes" as input; it has to look at `FormProgress.answers` (or the equivalent posted
value on the very same request) and decide independently. This is a strict reframe of "the client's
view of visibility is advisory, the server's view is binding" — advisory for UX, binding for storage,
required-ness, scoring and progress.

## 3. HTMX patterns for a same-page reveal

The idiomatic HTMX 2 approach to "answering this question reveals more of the page" is:

- **`hx-trigger="change"`** on the triggering input (radio/select), posting to an endpoint that
  re-renders the container of dependent questions. HTMX's own trigger modifiers matter here: `changed`
  (only fire when the value actually changed, not on every event) and `delay:` (debounce — wait N ms,
  resetting the timer if the event repeats) — see [`hx-trigger`
  docs](https://htmx.org/attributes/hx-trigger/). A radio group flicked through quickly without
  debouncing fires one request per click; with `delay:150ms` (or similar) only the settled choice fires.
- **`hx-sync`** governs what happens to *overlapping* in-flight requests from the same trigger — e.g. a
  learner clicks "Yes" then "No" before the first response lands. Strategies are `drop` (ignore the new
  request while one is in flight — the default), `abort` (cancel one side or the other depending on
  timing), `replace` (cancel the in-flight request, start the new one — the natural choice here, so the
  displayed reveal always matches the *last* click rather than a stale one that happened to return
  later), and `queue` variants (`first`/`last`/`all`) that serialise requests instead of dropping them.
  See [`hx-sync` docs](https://htmx.org/docs/#attributes) and the [hx-trigger
  reference](https://htmx.org/attributes/hx-trigger/) for the `queue` option nested inside a trigger
  spec. For a same-page reveal, `hx-sync="this:replace"` (or `closest form:replace`) paired with
  `delay:150ms` is the combination that avoids both a flood of requests and a race where an earlier,
  slower response overwrites a later, faster one.
- **Out-of-band swaps (`hx-swap-oob`)** let one response update two unrelated parts of the DOM at once
  — the reveal container *and*, e.g., a progress indicator (FLS already has one: `answered_counts` in
  `paging.py` feeds a live "N of M answered" readout). The response for the branch-question POST can
  carry the revealed fieldset as the primary swap target and the progress indicator markup tagged
  `hx-swap-oob="true"` alongside it, updating both without a second request. See [HTMX — Updating Other
  Content](https://htmx.org/examples/update-other-content/) and [`hx-swap-oob`
  docs](https://htmx.org/attributes/hx-swap-oob/).
- **`hx-preserve`** matters if the reveal has to happen *without* discarding what the learner has
  already typed elsewhere on the page — it keeps an element (matched by a stable `id`) untouched across
  a swap of an ancestor. Its own docs warn it does not preserve caret position/focus for `<input
  type="text">`, and recommend the `morphdom` extension where that granularity matters
  ([`hx-preserve` docs](https://htmx.org/attributes/hx-preserve/)). Because FLS's page swap here would
  be scoped to the *reveal container itself* (not the whole page), `hx-preserve` is largely unnecessary
  if the swap target is narrow — the safer default is "swap only the fieldset that changes," not "swap
  the whole page and preserve everything else."
- **`hx-select`** (pull a fragment out of a larger response) and **`hx-swap`** (`outerHTML` is FLS's
  established default per `claude_plugins/django-stack/skills/htmx/SKILL.md`) apply the same way any
  other FLS HTMX partial does — nothing branch-logic-specific changes the underlying convention.

**What it costs in requests**, concretely: an unthrottled `hx-trigger="change"` on a radio group fires
once per click as the learner explores options (a common real complaint, echoed in HTMX
dependent-dropdown write-ups — see [HTMX Dependent Dropdowns: 5 Strategies I Learned the Hard
Way](https://medium.com/@almatins/htmx-dependent-dropdowns-5-strategies-i-learned-the-hard-way-91337775f0d6),
which catalogues exactly this class of problem and the trigger/debounce/sync fixes for it). `changed
delay:150ms` plus `hx-sync="this:replace"` collapses that to roughly one request per settled decision.

Real write-ups of progressively-enhanced, HTMX-driven forms are candid about the remaining friction:
Rafael Epplée's account of building progressively-enhanced HTMX forms notes that "updating the UI in
response to user interactions will often require a roundtrip to the server," that *transient state*
(input not yet persisted) has to be carried across that roundtrip deliberately (via query params or
resubmitted form values, not assumed to survive), and that multiple forms/buttons on one page need
explicit handling (`formaction`, distinct `name`/`value` pairs) to route correctly — his conclusion is
to build the no-JS version first and add HTMX after, precisely so the round-trip cost and the
state-carrying problem are visible early rather than retrofitted
([rafa.ee — Building Progressively Enhanced Forms Using htmx](https://www.rafa.ee/articles/progressive-enhanced-forms-htmx/)).

## 4. Alpine under a CSP build

The project's own resource (`claude_plugins/django-stack/resources/alpine_csp_build.md`) is unambiguous
and matches Alpine's official CSP documentation: the `@alpinejs/csp` build "forbids inline JavaScript in
Alpine directives" — no inline object literals in `x-data`, no inline assignment in `x-on:click`, no
inline ternary in `:class`. Every `x-data` value must be a **registered component name** resolved via
`Alpine.data()` in a project JS file loaded *before* the CSP build script; an unregistered name silently
fails ([Alpine.js — CSP build](https://alpinejs.dev/advanced/csp)).

What survives for a same-page reveal under this constraint:

- **`x-show`** with a **bare property name** (e.g. `x-show="employerRevealed"`) or its negation
  (`x-show="!employerRevealed"`) is explicitly confirmed to work — "a simple property reference (no
  expression) works in the CSP build," per the project's own resource, consistent with Alpine's official
  CSP documentation that method calls, ternaries and assignments are what's excluded, not property
  references themselves.
- **`Alpine.data()` components** hold all the logic: reading the trigger value, deciding
  `employerRevealed`, and exposing it as a plain property `x-show` can read.
- **Passing rule/answer data in from Django** has to go through `data-*` attributes (read in `init()`
  via `this.$el.dataset...`) or a `<script type="application/json">` block parsed in `init()` — never
  interpolated into an `x-data` expression, because `x-data` cannot carry an inline object literal under
  this build. This is exactly the pattern FLS's own resource documents for "Passing data from Django
  templates to Alpine," and it is the only sanctioned channel for shipping a rule (or a snapshot of
  which questions are currently visible) to the client.
- **What doesn't work**: any inline expression evaluating the rule itself in a directive — e.g.
  `x-show="answers.employer_pays == 'yes'"` would not run under this build; the comparison has to happen
  inside a registered method (`x-show="employerRevealed"` where `employerRevealed` is computed in JS
  from data read off `data-*` attributes), not written as markup.

This has a direct implication for posture (c): if FLS ever shipped a client-side rule evaluator, it
could not be markup-level inline logic — it would have to be a small interpreter registered as (part of)
an `Alpine.data()` component, reading rule JSON from a `<script type="application/json">` block and
exposing the computed visible-set as plain reactive properties for `x-show` to reference. That is more
code than a naive "put the condition inline in the template" approach would suggest, and it is exactly
the kind of interpreter that has to be kept in lock-step with the Python one (§1's contract-test /
compile-to-predicate answers apply here specifically).

## 5. No-JS degradation

A server-side, page-boundary evaluation gives a **fully correct** experience with JS off: the server
decides what page comes next based on stored answers, the learner sees exactly the questions that apply
to them, nothing is ever silently missing or wrongly required. The cost is one that GOV.UK's own service
manual explicitly accepts as the *default*, not a degraded fallback: "an extra page" between the trigger
question and its dependents, navigated by an ordinary "Continue" submit — no reveal mechanism needed at
all, because the branch is decided at a page boundary.

This is precisely GOV.UK's stated design answer, and it is stronger than "acceptable no-JS
degradation" — it's their starting recommendation for *any* form, JS or not:

> "Start by splitting the form across multiple pages with each page containing just one thing... this
> approach... helps you to... handle branching questions and loops."
> — [GOV.UK Service Manual — Structuring a form](https://www.gov.uk/service-manual/design/form-structure)
> and [Design in Government — One thing per page](https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/)

And, specifically about the same-page reveal component GOV.UK *does* offer (conditionally revealed
radios/checkboxes), their own component guidance pulls in the opposite direction from "always reveal
inline":

> "Keep it simple. If the related question is complicated or has more than one part, show it on the
> next page in the process instead."
> — [GOV.UK Design System — Radios, conditionally revealing content](https://design-system.service.gov.uk/components/radios/)

GOV.UK also documents a real, unresolved accessibility gap in the same-page reveal pattern itself: "Users
are not always notified when a conditionally revealed question is shown or hidden. This fails WCAG 2.2
success criterion 4.1.2 Name, role, value" (same page), tempered by "screen reader users could still
answer simple conditionally revealed questions without difficulty" but confused by complex, multi-part
ones — see also [Accessibility in Government — An update on the accessibility of conditionally revealed
questions](https://accessibility.blog.gov.uk/2021/09/21/an-update-on-the-accessibility-of-conditionally-revealed-questions/).
"A set of employer questions" is exactly the "more than one part" case GOV.UK's own guidance says to
route to a new page rather than reveal inline.

**Judged honestly**: this design answer — trigger question alone on its own page — does not merely make
client-side evaluation *cheaper to skip*, it removes the need for it. If the branch is always decided at
a page boundary, there is no same-page reveal to build client-side logic for in the first place; the
"where is the condition evaluated" question collapses to "the server, when it decides which page comes
next," which is posture (a) by construction. Client-side evaluation only becomes *necessary* (rather
than a pure UX nicety) once the design insists on same-page reveals for compound follow-ups — which is
exactly the case GOV.UK's own guidance advises against.

## 6. Progressive enhancement in practice

Teams that ship conditional forms with a server-rendered baseline plus a JS layer report keeping in sync
the things listed in §1 and §3: the rule/schema itself (Form.io's answer is to make the schema the one
artefact both the renderer and the validator read —
[form.io](https://form.io/features/form-conditional-logic-form-validation/)), and, in the HTMX-specific
accounts, *transient state* — input the learner has typed but not yet persisted, which has to be
threaded through the round trip explicitly (query params, resubmitted values) rather than assumed to
survive a swap ([rafa.ee](https://www.rafa.ee/articles/progressive-enhanced-forms-htmx/)). What they
give up, in the htmx-first accounts, is the SPA assumption that all UI state lives in memory
client-side; correctness comes from treating the server round trip as the normal path and JS as
optional acceleration on top of it, not the other way around — echoed by htmx's own framing that
`hx-boost`-style enhancement "degrades gracefully if JavaScript is not enabled: the links and forms
continue to work, they simply don't use ajax requests" (general htmx progressive-enhancement framing,
[htmx documentation](https://htmx.org/docs/)).

**Evidence on how much a round trip per reveal actually hurts perceived quality** is thin and mostly
qualitative rather than measured. What the sources above establish is directional, not quantified: GOV.UK
ships full-page-per-question by default across government services used at very large scale, without
treating the per-question page load as a UX defect to be engineered away — their guidance frames the
extra page as *the* right structure (better on mobile, better for errors, better for save-and-resume),
not a compromise. No source found in this research reports a controlled measurement of "reveal via
round trip" versus "reveal via client JS" perceived-quality difference for a form of FLS's scale (a
handful of conditional fields, not a dense multi-branch wizard). The honest conclusion is: the round-trip
cost is real but small (one extra page load, well within normal page-to-page navigation a learner is
already doing throughout the form), and no evidence surfaced here says it is large enough to justify the
either the client-authoring cost of Alpine CSP rule evaluation or the drift risk of a duplicated rule
engine — see the framing in §1 and §4.

## What this suggests for FLS

FLS's existing surfaces already assume, structurally, that visibility and required-ness are recomputed
server-side per request from stored data — `unanswered_required_on_page` and
`unanswered_required_in_form` never read anything but `FormProgress.answers` and the current POST; the
page-jump nav (`build_page_links`) and `resume_page_number` decide "how far can this sitting go" purely
from stored answers and `furthest_page_reached`. Branch logic is a natural extension of that same shape,
not a new architectural layer: **"which questions belong on this page" becomes one more thing
`form_fill_page` / `application_form_page` derive from `FormProgress.answers` before calling
`page_questions`**, no different in kind from how they already derive "which questions are still
required" before calling `unanswered_required_on_page`.

The recommendation is **posture (a): evaluate the condition server-side, at page boundaries, and design
the content so that the trigger question sits alone on its own page** when its dependents are a set
(the "employer pays" → several employer questions case named in the brief) rather than a single field.
That single design choice — one question, one page, branch decided before the next page renders —
removes the need for a same-page reveal, and with it removes the need for any client-side rule
evaluator at all. It costs the learner one extra page in the flow, which is the default GOV.UK ships at
government scale, not a fallback tier. It costs FLS the least code of the three postures, and it cannot
drift: there is exactly one rule evaluator, and it is the one that already gates storage.

The **existing file-upload HTMX partial is the right precedent for what NOT to over-generalise from**:
`partial_question_file_upload` is a same-page, single-question, single-purpose partial update that
never has to decide "what else on this page depends on this," and its own server-side authority is
absolute (`unanswered_required_on_page` checks the stored row, never anything the partial's markup
implies was uploaded). It shows same-page HTMX partials are an established, working pattern in this
codebase — the recommendation isn't "FLS can't do a same-page reveal," it's "the file upload partial is
narrow-and-safe because it never needs a rule engine behind it, and a same-page conditional reveal for a
*set* of employer questions would need exactly the two-place-evaluation machinery in §1, which is a much
larger commitment than the file-upload partial's shape suggests." Surveys, which the brief also names as
a target, are lower stakes than an application's required-field enforcement, and may tolerate a
same-page reveal (single field, e.g. "please specify" free text after "other") — that is squarely
GOV.UK's own "keep it simple" case for an inline reveal, not the "route to the next page" case.

**A phase-1 that ships without any client-side evaluation** looks like: the condition lives as data on
the `Form`/`FormPage`/`FormQuestion` model layer (out of scope for this document, but the shape is
implied by everything above — something `paging.py`-adjacent that both the page-selection logic and
`unanswered_required_on_page`/`unanswered_required_in_form` can call); page flow (`resume_page_number`,
`build_page_links`, `form_fill_page`, `application_form_page`) consults it to skip pages whose trigger
condition isn't met and to compute the required set on a page that *does* include a conditionally-shown
question; no Alpine, no client rule interpreter, no same-page HTMX reveal endpoint. That is a reasonable
place to stop for the stated first-version scope (application forms and surveys, explicitly not
quizzes): it is correct with JS off, correct under any POST, and adds no new failure surface beyond
"which page is next" — a question FLS's page-flow code already exists to answer. Same-page reveals, if
wanted later for the survey case's simpler single-field pattern, can be added incrementally on top
without revisiting this decision, because they would be scoped to cases GOV.UK's own guidance already
calls out as safe to keep simple.

---
status: ok
reason: Completed all six research sub-questions with codebase grounding (paging.py, models.py, views.py, file-upload partial, Alpine CSP resource, HTMX skill) and cited web sources (OWASP, HTMX docs, Alpine docs, GOV.UK Service Manual/Design System, Form.io, rafa.ee); closed with an FLS-specific recommendation (posture (a), page-boundary evaluation) and a phase-1 scope description without an implementation plan.
