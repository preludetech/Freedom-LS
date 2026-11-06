# Research: learner-facing UX of branching, and its accessibility

Scope: how conditional visibility ("if employer pays, show employer questions") should behave for
the learner sitting a `Form` through `learner_interface::form_fill_page` or the
`course_applications` shell, given the existing surfaces: the page-jump nav (`paging.build_page_links`),
the `answered / total` progress indicator (`paging.answered_counts`), global
`FormQuestion.question_number()`, and the application shell's check-your-answers page.

---

## 1. Progressive disclosure patterns

**GOV.UK's baseline position is "one thing per page," not conditional reveal.** The design system's
guidance is explicit that question pages — one question, one page — should be the starting point for
any UK government service form, and that conditional reveal is a fallback, not a default:
"if you need to ask questions in your service, you should always start with one thing per page,"
moving to alternatives like progressive disclosure only when user research shows it is needed
([GOV.UK Design System, one thing per page](https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/);
[question pages](https://design-system.service.gov.uk/patterns/question-pages/)).

**Where GOV.UK does allow same-page reveal, it is narrowly scoped.** The `govuk-radios__conditional`
pattern (and its checkbox equivalent) is documented for exactly one case: revealing a single,
simple, related input when a radio or checkbox is selected — e.g. a phone number field appearing
under "Contact me by phone." The component's own guidance states explicit **do-nots**:

- Don't reveal more than a single input — "otherwise the revealed section should not be in a
  show-and-hide but rather in its own form in the next step of the process."
- Don't use it for complicated, multi-part follow-up questions — testing found screen reader users
  managed simple reveals fine but were confused by complex ones.
- Don't conditionally reveal content that isn't itself a question (no stray paragraphs, warnings, or
  non-input content).
- Don't attach a conditional reveal to inline yes/no options placed side by side.

([GOV.UK Design System, Radios component](https://design-system.service.gov.uk/components/radios/))

**NNG's progressive disclosure principle applies directly, with the same warning against overuse.**
Jakob Nielsen's rule — show the few most important options up front, the rest on request — improves
learnability, efficiency, and error reduction, but "designs exceeding two disclosure levels typically
suffer poor usability," and hiding something users need often just relocates complexity rather than
removing it ([NN/g, Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)).

**Baymard's empirical finding favours same-page reveal specifically for hiding *optional* fields
behind a link**, not for branching a form's structure: hiding an optional field (e.g. address line 2)
behind a "+ Add" link reduces perceived form length, and eye-tracking showed users reliably notice
such links before engaging them (
[Baymard, Address Line 2](https://baymard.com/blog/address-line-2)). This is a different shape of
problem from FLS's "employer pays → 5 employer questions": it is disclosure of an optional extra
field on the *same* question, not a set of *new, required* questions gated on an answer.

**When same-page reveal beats a new page, and vice versa, synthesised from the above:**

| Same-page reveal is right when… | A new page (or its own step) is right when… |
|---|---|
| Exactly one follow-up input, itself simple (a single text/number/select field) | More than one follow-up question is triggered |
| The follow-up is tightly bound to the triggering answer, read as one thought ("contact by phone" → phone number) | The follow-up is really a new topic (an "employer details" section, not one extra field) |
| The trigger is a distinct choice, not one of a visually-adjacent yes/no pair | The reveal would need multi-part or free-text content that AT testing shows confuses users |

Applied to FLS's stated primary use case — "will your employer pay?" revealing a *set* of employer
questions — this is squarely the "own step" case per GOV.UK's own rule, not a same-page
`govuk-radios__conditional`. That argues for **branching at the page/section level being the primary
mechanism FLS should design for**, with single-field same-page reveal (if offered at all) reserved
for the narrow one-input case.

---

## 2. Accessibility

This is where most of the real design constraint sits, because FLS's runner is a plain server-rendered,
POST-per-page fieldset (see `question.html`) with a CSP Alpine build (no inline expressions) — so any
same-page reveal has to be done with explicit `Alpine.data()` components and explicit ARIA wiring,
never assumed.

### 3.2.2 On Input (change of context)

WCAG 3.2.2 requires that changing a form control's value must not, by itself, trigger a *change of
context* (a shift in focus, a new window, content that changes the meaning of the page) unless the
user was told in advance that this control behaves that way. Revealing or hiding a block of new
required questions on selection is close to the line WCAG draws, but the mainstream reading — and the
one GOV.UK's own use of `govuk-radios__conditional` relies on — is that revealing content **within the
same page, without moving focus or navigating**, is not of itself a 3.2.2 violation, whereas an
automatic page navigation or focus jump triggered purely by selecting a radio value would be
([Understanding SC 3.2.2](https://www.w3.org/WAI/WCAG20/Understanding/on-input);
[WebAIM, Change of Context vs Change of Content](https://webaim.org/blog/decoding-wcag-change-of-context/)).
Practically: FLS must never auto-advance to the next page, or auto-submit, purely because a radio
answer was selected — the learner must still press Continue.

### 4.1.3 Status Messages, and what GOV.UK actually found

4.1.3 (AA) requires that a status message — content that changes without a focus change — be
programmatically determinable so it is announced without requiring focus to move onto it, typically
via `aria-live`, `role="status"`, or `role="alert"`
([Understanding SC 4.1.3](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)). GOV.UK's
own accessibility team investigated exactly this for conditional reveals and found:

- `aria-expanded` **is not a valid ARIA attribute on radio/checkbox inputs** per the ARIA spec (it is
  only valid on elements with certain roles), so using it there is technically non-conformant — yet
  some screen readers still surfaced *something* to users when it changed, which the GOV.UK team
  believed incidentally helped signal that something changed
  ([alphagov/govuk-frontend#979](https://github.com/alphagov/govuk-frontend/issues/979);
  [GOV.UK a11y blog, update on conditionally revealed questions](https://accessibility.blog.gov.uk/2021/09/21/an-update-on-the-accessibility-of-conditionally-revealed-questions/)).
- The finding that mattered most in practice: **screen reader users could answer simple, single-input
  conditional reveals without difficulty even without an explicit announcement**, but were confused by
  complex, multi-part ones — regardless of ARIA wiring. GOV.UK, after consulting the ARIA Working
  Group and the Digital Accessibility Centre, concluded the fix was **restricting scope (single input
  only), not adding more ARIA** — i.e. simplicity beat instrumentation.
- GOV.UK's association mechanism is `data-aria-controls`/`aria-controls` from the controlling radio to
  the id of the revealed `<div>` — a structural association, not a live-region announcement.

The ARIA Authoring Practices Guide's **Disclosure (Show/Hide) pattern** is the more general-purpose
reference and is unambiguous about which pair of attributes belongs on the *controller*: a `<button>`
(not a radio) carries `aria-expanded="true|false"` and, optionally, `aria-controls` pointing at the id
of the revealed region. This is the right pattern to reach for when the FLS trigger is a genuine
toggle/disclosure control; it is the *wrong* pattern to bolt onto a radio input, which is exactly the
mistake GOV.UK made and then walked back
([WAI-ARIA APG, Disclosure pattern](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/);
[Adrian Roselli, Disclosure Widgets](http://adrianroselli.com/2020/05/disclosure-widgets.html)).

**`aria-expanded`/`aria-controls` vs `aria-live` — different jobs, not alternatives:**
- `aria-expanded` on the controller announces *state* ("expanded"/"collapsed") when a screen reader
  user is *on* that control — it says nothing to a user who is elsewhere on the page when the change
  happens.
- `aria-live` (or `role="status"`/`role="alert"`) on the *revealed region itself* announces new content
  to a user *regardless of where their focus currently is* — this is the mechanism that actually
  satisfies 4.1.3 for a change that happens without moving focus.
- Neither substitutes for the other: a toggle button legitimately wants both (`aria-expanded` on
  itself, and if the revealed content is dynamically injected rather than merely unhidden, an
  `aria-live` region around it) — but GOV.UK's own experience is a caution against over-instrumenting
  a *radio-driven* reveal, where simplicity of the reveal (one field) mattered more than the ARIA.

### 1.3.2 Meaningful Sequence and 2.4.3 Focus Order

1.3.2 requires that when reading order carries meaning, the DOM order (which is what a screen reader
walks) matches it — the recommended technique is literally "make the DOM order match the visual
order" ([Understanding SC 1.3.2](https://www.w3.org/WAI/WCAG22/Understanding/meaningful-sequence.html)).
For FLS this means a revealed employer-questions block must be inserted **immediately after its
trigger question in the DOM**, not appended at the end of the fieldset/page and pulled up visually
with CSS — otherwise a sighted mouse user and a screen reader user read the page in two different
orders.

2.4.3 requires that focusable elements receive focus in an order that preserves meaning and operation
when a page can be tab-navigated. For revealed content this cashes out as two established techniques
([Understanding SC 2.4.3](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html)):

- **SCR26** — insert dynamically-added content into the DOM immediately following the element that
  triggered it, so Tab order naturally flows into it without a manual focus jump.
- When content is inserted far from the trigger (not applicable if SCR26 is followed) a script must
  reorder focus, which is more fragile — so the practical rule for FLS is: **keep the revealed
  question block adjacent, in DOM order, to the question that reveals it.** This is also exactly what
  keeps `question_number()`'s "walk the pages/questions in order" logic sound if it is later asked to
  reason about which questions are "next" (see §4).

### Focus management on appear/disappear

Best-practice guidance (APG-derived, summarised across multiple accessibility guides) is consistent:

- When content **appears**: don't forcibly move focus off the control the user is already interacting
  with just because content appeared nearby — let Tab order carry them into it naturally (this is
  SCR26 again). Forcing a focus jump the instant a radio is checked is itself a 3.2.2-adjacent
  surprise.
- When content **disappears** (the learner changes their mind — see §5): if focus was inside the
  removed region when it vanishes, focus must be moved somewhere sane — back to the triggering
  control, or to the nearest preceding element — never left to silently fall back to `<body>`, which
  screen reader users experience as "losing their place" entirely
  ([Orange a11y guidelines, Dynamic focus](https://a11y-guidelines.orange.com/en/articles/dynamic-focus/)).

### `display:none` vs `hidden` vs `disabled` vs DOM removal — genuinely different for AT

These are not interchangeable, and the difference matters directly for FLS's `save_answers()`, which
trusts `has_submitted_answer(question, post_data)` against whatever the browser POSTs:

- **`display:none` / the `hidden` attribute**: removes the element from the accessibility tree —
  invisible and unannounced to screen readers, not focusable, not tabbable. Correct choice for "this
  question does not currently apply."
- **`disabled`**: the control is visible (typically greyed out) but **not focusable and usually not
  announced as present at all to many screen readers** navigating by Tab; a value on a `disabled`
  control is also **not submitted** with the form. This is a materially different state from hidden —
  it says "this exists, but you may not touch it," where hidden says "this does not currently exist
  for you."
- **`aria-hidden="true"` on a focusable element is a known trap**: the element stays in the Tab order
  (focusable) but is invisible to assistive tech, meaning a screen reader user can tab into an empty,
  unannounced control. WebAIM specifically warns against this combination
  ([WebAIM, Invisible Content](https://webaim.org/techniques/css/invisiblecontent/)).
- **The concrete submission trap for FLS**: a question hidden only visually (e.g. CSS
  `visibility:hidden` or an Alpine `x-show` that leaves the DOM node present, inputs and all) is
  **still present in the POST body**. FLS's `save_answers()` iterates `questions` passed in by the view
  and calls `has_submitted_answer` against `post_data` — it does not itself know a question was
  supposed to be hidden by branch logic. If the branch-logic implementation only toggles CSS
  visibility client-side and the server still treats the question as "on this page," a learner who
  answered "no, employer doesn't pay" could still have stray employer-question values sitting in
  `post_data` (browser autofill or a value entered before switching the radio) and get them **silently
  saved as answers** unless the server-side page-render explicitly excludes hidden questions from the
  set it persists. This is the single most important accessibility-adjacent correctness risk hidden
  vs. disabled raises for this codebase, independent of screen readers: **whichever mechanism hides a
  question, the server's decision about which questions to persist must be re-derived from the
  branch condition at submit time, not merely from what happened to be visible in the browser.**

---

## 3. "Visible but disabled" / locked state

**The weight of guidance is against showing a not-yet-relevant question as visible-but-disabled.**
Grounds, converging from several sources:

- **Accessibility cost is real and specific**: disabled controls are typically not focusable, are
  often skipped by screen reader Tab navigation entirely (so their existence isn't even announced),
  and the WCAG contrast requirements for text explicitly **exempt inactive/disabled UI components** —
  so a greyed-out control legitimately may not meet the contrast ratio a normal control would need,
  compounding the problem for low-vision users
  ([Smashing Magazine, Usability Pitfalls of Disabled Buttons](https://www.smashingmagazine.com/2021/08/frustrating-design-patterns-disabled-buttons/)).
- **NN/g's position on disabled controls generally**: reserve `disabled` for a strong, specific reason
  (preventing a duplicate submission, signalling an in-flight process) — not as a general "not
  available yet" indicator — because a disabled control communicates that something is wrong without
  explaining what, leaving users to guess.
- **GOV.UK's position is the most directly on point for FLS's exact scenario** (a multi-step form
  where later information depends on earlier steps): "do not use the disabled state to display
  previously submitted information, as this can confuse users as they may not realise that they
  cannot change the information" — disabled inputs are often visually indistinguishable enough from
  active ones, and don't explain *why* they can't be touched. The recommended alternative for a
  multi-step form is to **render prior-step information as plain read-only text**, not as a disabled
  form control, and — symmetrically for FLS's case — to simply **not show a question at all** rather
  than show it locked.

**Is there a legitimate case for showing a learner a locked question?** The research surfaces one
narrow, defensible case and it is not FLS's: sequencing UI (e.g. a wizard's step list) where a *step
title* is shown-but-not-yet-reachable purely for orientation ("Step 4: Payment" greyed out because
steps 1–3 aren't done) — i.e. showing the *shape* of the journey, never a specific input control
locked. Even GOV.UK's step-by-step navigation pattern, which does show a whole journey up front,
shows steps as **links to content**, not as disabled form fields. Translated to FLS's nouns: it would
be defensible for the page-jump nav to show a page's *title* greyed out and unreachable (which
`build_page_links`'s `is_accessible` flag already does for pages beyond the accessibility limit — see
`paging.page_accessibility_limit`), but it would not be good practice to render an employer question
itself, inputs and all, in a disabled state on a page the learner can already reach.

---

## 4. Orientation under a variable path

**GOV.UK's own guidance on progress indicators starts from scepticism, not from "add one."** The
design system recommends testing without a progress indicator first, and only adding "a simple step
or question indicator" if the form's order/type/number of questions can't be simplified enough to do
without one. Crucially: "only include the total number of questions if you can do so reliably," and
the indicator must be kept in sync with which question the user is actually on and how many remain
([GOV.UK Design System guidance, summarised via community/pattern documentation — see
Question pages](https://design-system.service.gov.uk/patterns/question-pages/) and progress-indicator
discussion at [Justice digital pattern library, Progress tracker](https://design-patterns.service.justice.gov.uk/components/progress-tracker)).
The load-bearing implication for a form with branch logic: **the moment "total questions" depends on
answers already given, a naive static "Question 7 of 20" is a reliability violation of GOV.UK's own
rule** — 20 was never a promise the form can keep once conditional questions are skippable. The two
GOV.UK-compatible ways out are (a) don't show a *count* at all, show only *step names already passed*
(a step tracker rather than a fraction), or (b) recompute the denominator live from the current
answer set, on every page, rather than freezing it at form start.

**FLS's own `answered_counts()` already has the seam this argues for.** It returns
`total_question_count = count_form_questions(form)` — a static count of every `FormQuestion` in the
form, independent of any answer. Once branching exists, this denominator becomes exactly the kind of
unreliable total GOV.UK warns against: a learner who answers "employer does not pay" and skips five
questions will see `answered / total` understate their real completion, because `total` still counts
questions they will never be asked. The fix implied by the research is not cosmetic — `total` needs to
mean "questions this learner's current answers imply they'll see," recomputed as answers change, the
same way GOV.UK says the total must be recomputed rather than fixed at 20.

**Global question numbering (`question_number()`) has an equivalent, sharper problem.** It is used
in the legend (`{{ question.question_number }}.`), in `data-testid="question-number-N"`, in the
required-indicator testid, and in `unanswered_required_message()`'s "Question 5 needs an answer."
Renumbering live — so that skipping a branch's questions makes what was "Question 6" become
"Question 5" — matches user expectation (a hidden question shouldn't leave a numbering gap) but comes
with two concrete costs the research surfaces:
- It breaks the stability of `data-testid="question-number-N"` as an identifier across different
  answer paths of the *same* form — anything (tests, saved deep-links, "you are here" bookmarking)
  that assumes question N is a fixed identity for a fixed `FormQuestion` breaks once N is
  answer-dependent.
- Products that do this well (see the survey-tool complaints in §6) recompute numbering *only at
  page-render time from the current answer set*, never client-side speculatively before an answer is
  saved — because a number that changes based on an unsaved, in-progress radio selection is exactly
  the kind of "jumpy" experience users complain about.

The GOV.UK-aligned recommendation is therefore to keep `question_number()`'s current behaviour (a
stable ordinal position within the *full, unbranched* form) as the **identity** used for testids and
constants, and introduce a *separate*, answer-derived "visible position" (e.g. "Question 4 of 12
visible") only for the human-facing legend text and progress copy — not conflate the two.

**Page-jump nav when a page is skipped.** `build_page_links` currently lists every `FormPage` in the
form unconditionally, with `is_accessible` gating only on *reached-so-far*, not on *relevance*. Once
whole pages can be branch-conditional (e.g. an "Employer Details" page that only applies when the
learner said yes), the research argues, per GOV.UK's disabled-state guidance above, that a
now-irrelevant page should be **omitted from the page-jump nav entirely**, not shown disabled/greyed —
the same logic that says don't show a locked question applies to a locked page link.

---

## 5. Back-navigation and changing your mind

The research did not surface a single canonical "conditional logic + change your mind" pattern from
GOV.UK (their check-your-answers documentation is the closest fit, and is written for the general
case, not specifically for branch-triggered content), so this section reasons from what does exist,
attributed accordingly.

**GOV.UK's check-your-answers pattern's own account of edits**: a "Change" link returns the user to
the relevant page, and *"the user should be returned to the 'Check your answers' page once they've
updated the information (and any other questions triggered by their updated response)"* — i.e. GOV.UK's
own pattern explicitly anticipates that editing one answer can change which *other* questions apply,
and treats re-visiting those triggered questions as part of the same edit flow, not a silent discard
([GOV.UK Design System, Check answers](https://design-system.service.gov.uk/patterns/check-answers/)).
The "Change" links themselves carry visually-hidden text so a screen reader announces *what* is being
changed ("Change employer name"), not just the word "Change" repeated — directly relevant to FLS's
check-your-answers page in `course_applications`.

**What this implies concretely for "yes, employer pays" → five answers → "no":**
- **Silent discard of now-irrelevant answers is the norm in well-built tools**, provided the learner
  is told what happened — GOV.UK's own pattern re-routes the learner *through* the now-irrelevant
  questions again rather than leaving stale answers sitting unseen in the database against a
  condition that no longer holds. Translated: FLS should not keep five `QuestionAnswer` rows for
  employer questions the learner has since made inapplicable — either delete them, or exclude them
  from every downstream calculation (progress counts, scoring, check-your-answers rendering) as if
  they didn't exist. Leaving stale rows silently affects `count_form_questions`/`answered_counts` and
  `score_category_value_sum`'s category sums in ways that are much harder to reason about than simply
  clearing the answers.
- **A destructive confirmation ("are you sure — this will discard your answers") is not the standard
  pattern GOV.UK uses**, and the general UX literature on confirmation dialogs treats them as noise
  when the action is reversible or low-stakes (answering the trigger question again immediately shows
  the same reveal, so nothing is unrecoverable — the learner can simply say "yes" again and the
  fields are empty but the questions are right back). A confirmation is more defensible only where the
  discarded content is *expensive to reproduce* — e.g. discarding a completed file upload or a long
  free-text answer specifically, rather than a short employer-name field.
- **Check-your-answers page behaviour when an edit invalidates a later section**: per the GOV.UK
  pattern above, the correct behaviour is that changing the triggering answer while on check-your-answers
  routes the learner back through the newly-applicable (or newly-inapplicable) questions before
  returning them to check-your-answers — the check-your-answers page itself should never silently
  show a stale answer for a question that current answers say is no longer being asked, and should
  never silently keep a required-question validation state for a question that no longer applies.

---

## 6. Common complaints

Recurring themes converge across survey-tool support content and UX write-ups on conditional/branch
logic, several with a direct FLS-relevant translation:

- **Logic that fires too eagerly / on the wrong granularity.** SurveyMonkey's own troubleshooting
  content names two of the most common author mistakes: skip logic applied per-answer-option in a
  1:1 way with no way to combine multiple conditions before routing, and **conflicting rules on a
  single page** — "a single respondent can't be skipped to two locations at once," which bites
  especially on multi-select (checkbox) questions where more than one selected option each carry a
  skip target ([SurveyMonkey, 3 Common Skip Logic Mistakes](https://www.surveymonkey.com/curiosity/3-common-skip-logic-mistakes/)).
  Direct translation for FLS's `checkboxes` type: if branch conditions are ever allowed on checkbox
  answers (not just radio/yes-no), the condition model has to have a defined, single answer for what
  happens when multiple selected options imply different reveals — this is exactly the ambiguity
  SurveyMonkey's own users hit.
- **Circular/backward logic that traps respondents.** The same source flags "circular logic" — routing
  a respondent backward — as a named failure mode that leaves people stuck unable to progress. For
  FLS's page-jump-nav-plus-linear-runner shape, this maps to: a branch condition must never be able to
  route a learner to a page *behind* one they've already passed the accessibility limit for, or the
  page-jump nav and the branch condition disagree about where the learner is "allowed" to be.
- **Terminology confusion between vendors** ("skip logic" vs "display logic" vs "logic jumps" meaning
  different things at SurveyMonkey vs Typeform) is itself a recurring complaint and a caution for FLS's
  own naming: whatever FLS calls its mechanism needs one name, used consistently in code, UI copy, and
  author-facing documentation, and it should be named for what it does at the layer it operates on
  (question-level vs page-level) rather than borrowed loosely from a competitor's term.
- **Support-forum-documented platform limits** — e.g. SurveyMonkey's own docs state skip logic is
  evaluated only "when you click Next," i.e. **not dynamically on the same page** — which is exactly
  the choice FLS is already leaning toward architecturally (POST-per-page), and is presented by
  SurveyMonkey itself as a known, accepted limitation rather than a bug, suggesting FLS need not treat
  "no live same-page branching" as a UX compromise so much as an industry-normal default.
- **Mobile keyboard/viewport problems when a field appears below the fold.** General mobile-forms UX
  literature documents the same recurring complaints regardless of source: a field revealed near the
  bottom of the viewport can be immediately obscured by the on-screen keyboard, especially on iOS
  (which overlays rather than resizes the viewport), and the page "jumps around" if the browser
  doesn't auto-scroll the newly-revealed field into view; recommended mitigations are scrolling the
  new field into view programmatically and avoiding `autofocus` into it (autofocus itself can trigger
  the keyboard unexpectedly, compounding the jump). This is a same-page-reveal-specific cost that a
  new-page approach avoids entirely, reinforcing §1's steer toward pages for anything beyond a single
  field.
- **Autofill breaking on reveal.** Browser autofill heuristics run against the DOM at the time a field
  becomes visible/interactive; a field injected or unhidden after page load is fed by autofill
  inconsistently across browsers — a widely-repeated frustration in general forms UX writing, not
  specific to any one survey vendor, and another argument for keeping same-page reveals to a single,
  simple field where the blast radius of an autofill miss is small.
- **Jumpy layout / scroll position moving under the user.** The complaint that the page visibly
  shifts (a later section jumps down, or the viewport scrolls) the instant a reveal or hide happens
  is the same failure this research's focus-management section (§2) addresses from the accessibility
  side — the practical fix (insert in DOM order right after the trigger, don't force scroll/focus
  unless the user asked to move on) fixes both the accessibility defect and the "jumpy" usability
  complaint at once.

---

## What this suggests for FLS

Stated against FLS's actual nouns and surfaces, not as an implementation plan:

- **Branch conditions should be modelled to gate whole pages (or a small number of adjacent
  questions), not scattered same-page single-field reveals, as the primary mechanism.** The stated
  use case — five employer questions appearing — is GOV.UK's own "don't use `govuk-radios__conditional`
  for this, give it its own step" case. Same-page reveal, if offered at all, should be a narrow,
  separate affordance limited to a single simple follow-up field, mirroring `govuk-radios__conditional`'s
  own restriction, not a general mechanism for revealing whole question sets.
- **Never auto-advance the page or auto-submit purely because a radio/checkbox value changed** (WCAG
  3.2.2) — Continue stays a deliberate, separate action, consistent with FLS's existing POST-per-page
  design.
- **A hidden (branch-excluded) `FormQuestion` must be excluded from persistence at the point the
  server decides what to save, not only hidden in the browser.** `FormProgress.save_answers()` must be
  called with the set of questions the current answers say actually apply, never with "every
  `FormQuestion` on this page" — otherwise stray POST data for a question the learner can no longer
  see (autofill, a value entered before switching the trigger answer) gets silently persisted as a
  `QuestionAnswer`. This follows directly from the `display:none`-vs-`disabled` submission trap in §2.
- **Never render a not-yet-relevant question as visible-but-disabled.** Per GOV.UK's own multistep-form
  guidance and NN/g's stance on disabled controls, a branch-excluded question should not be rendered
  at all on the page — not present in the fieldset, not present in the DOM as a disabled control. The
  one place a "locked, not yet reachable" visual state is defensible is the page-jump nav's existing
  `is_accessible: false` treatment of *pages ahead of where the learner has reached* — that convention
  should not be extended to individual questions within a page the learner is already on.
- **`answered_counts()`'s `total_question_count` needs to stop being a form-wide constant once branch
  logic exists.** It must be recomputed from the questions the learner's current answers actually
  imply will be asked, the same way GOV.UK insists a progress total must be "reliable" or omitted
  rather than fixed and wrong. A stale denominator that counts questions the learner will never see is
  the exact failure mode GOV.UK's progress-indicator guidance warns against.
- **`question_number()` should keep meaning "stable ordinal position in the full authored form"** and
  continue to back the `data-testid` identity and the required-question error message's question
  references — those need a fixed identity independent of which branch path is taken. Any
  answer-dependent "visible position" (e.g. "question 4 of 12 you'll actually see") the UI wants to
  show a learner should be a distinct, separately-computed value, not a change to what
  `question_number()` returns, so that skipping a branch's questions doesn't silently renumber the
  identifiers other code and tests already key off.
- **A page that becomes irrelevant because of a branch condition should disappear from
  `build_page_links`'s output, not appear there disabled.** This is the page-level version of the
  question-level rule above, and follows the same GOV.UK precedent (don't show a locked control; show
  only what currently applies).
- **On the application shell's check-your-answers page, changing an earlier answer that invalidates a
  later section should re-route the applicant through the now-different set of applicable questions
  before returning them to check-your-answers** — matching GOV.UK's own documented behaviour for its
  check-your-answers pattern — rather than silently deleting answers with no explanation or silently
  leaving stale answers visible for questions the current answers say no longer apply. A destructive
  "are you sure" confirmation is not indicated by any of the reference sources for content this cheap
  to re-enter (a handful of short fields); it would be more defensible only if branch-gated content is
  later extended to something expensive to redo, such as a file upload.
- **If a same-page reveal is built at all**, the revealed block must be inserted immediately after its
  triggering question in DOM order (not merely made visible via CSS while living elsewhere in the
  document) so that WCAG 1.3.2 (meaningful sequence) and 2.4.3 (focus order, via technique SCR26) hold
  without extra scripted focus management, and any Alpine component wiring it up should signal
  state via `aria-expanded` on the actual control element — reserving `aria-live` for cases where
  content needs announcing regardless of where a screen reader user's focus currently sits — following
  the APG's Disclosure pattern rather than repeating GOV.UK's own now-corrected mistake of attaching
  `aria-expanded` directly to a radio input.

---

## Sources

- [GOV.UK Design System — Radios (conditionally revealed content)](https://design-system.service.gov.uk/components/radios/)
- [GOV.UK Design System — One thing per page](https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/)
- [GOV.UK Design System — Question pages](https://design-system.service.gov.uk/patterns/question-pages/)
- [GOV.UK Design System — Check answers](https://design-system.service.gov.uk/patterns/check-answers/)
- [GOV.UK Design System — Step by step navigation](https://design-system.service.gov.uk/patterns/step-by-step-navigation/)
- [GOV.UK accessibility blog — An update on the accessibility of conditionally revealed questions](https://accessibility.blog.gov.uk/2021/09/21/an-update-on-the-accessibility-of-conditionally-revealed-questions/)
- [alphagov/govuk-frontend issue #979 — aria-expanded not valid on radios/checkboxes](https://github.com/alphagov/govuk-frontend/issues/979)
- [Fuzzy Logic — The accessibility of conditionally revealed questions (on GOV.UK)](https://fuzzylogic.me/posts/the-accessibility-of-conditionally-revealed-questions-on-gov.uk/)
- [W3C WAI-ARIA APG — Disclosure (Show/Hide) pattern](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/)
- [Adrian Roselli — Disclosure Widgets](http://adrianroselli.com/2020/05/disclosure-widgets.html)
- [W3C — Understanding SC 3.2.2 On Input](https://www.w3.org/WAI/WCAG20/Understanding/on-input)
- [WebAIM — Decoding WCAG: "Change of Context" and "Change of Content"](https://webaim.org/blog/decoding-wcag-change-of-context/)
- [W3C — Understanding SC 4.1.3 Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)
- [W3C — Understanding SC 1.3.2 Meaningful Sequence](https://www.w3.org/WAI/WCAG22/Understanding/meaningful-sequence.html)
- [W3C — Understanding SC 2.4.3 Focus Order](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html)
- [Orange digital accessibility guidelines — Dynamic focus](https://a11y-guidelines.orange.com/en/articles/dynamic-focus/)
- [WebAIM — CSS in Action: Invisible Content Just for Screen Reader Users](https://webaim.org/techniques/css/invisiblecontent/)
- [NN/g — Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
- [NN/g — Why Disabled Buttons Hurt UX (and How to Fix Them)](https://www.nngroup.com/videos/why-disabled-buttons-hurt-ux-and-how-to-fix-them/)
- [Smashing Magazine — Usability Pitfalls of Disabled Buttons, and How to Avoid Them](https://www.smashingmagazine.com/2021/08/frustrating-design-patterns-disabled-buttons/)
- [Baymard Institute — Form Usability: Getting Address Line 2 Right](https://baymard.com/blog/address-line-2)
- [SurveyMonkey — 3 Common Skip Logic Mistakes: How To Fix and Avoid Them](https://www.surveymonkey.com/curiosity/3-common-skip-logic-mistakes/)
- [SurveyMonkey — Troubleshooting Skip Logic Issues](https://help.surveymonkey.com/en/surveymonkey/create/troubleshooting-skip-logic/)
- [Typeform Community — Visibility / skip logic](https://community.typeform.com/build-your-typeform-7/visibility-skip-logic-6448)
- [UK Parliament Design System — Designing forms (disabled-state guidance for multistep forms)](https://designsystem.parliament.uk/how-tos/designing-forms/)

---

status: ok
reason: research complete; all six sub-topics covered with cited sources and translated to FLS's own model/field vocabulary in the closing section
