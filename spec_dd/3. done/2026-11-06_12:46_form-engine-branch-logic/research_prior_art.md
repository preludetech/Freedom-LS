# Research: prior art for conditional pages and questions

What has already been tried or decided about conditional pages and questions, in this repo and in public
systems. The five sibling `research_*.md` files cover how conditions are modelled, evaluated, authored,
and what happens to answers. This one does not repeat them. It records the history: what was decided,
deferred or rejected, and what changed later.

Limits of this pass. No shell was available, so there was no `git log` and no commit hashes. The repo
findings below are cited by spec path, and every one comes from the spec archive. Web findings that
come from search snippets or community forums are marked as such.

## 1. Here: this repo

### 1.1 Conditionals were considered once and deliberately deferred

The only earlier discussion is in the done spec
`spec_dd/3. done/2026-09-10_09:45_simple-application-forms/`.

- `research_question_types_and_validation.md` section 5, "Conditional questions". It found that
  nothing in `form_engine` supported conditional display: `FormQuestion` had no "depends on" or
  "shown if" field, and `FormPage.children()` returned every question and content block in `order`.
  The Alpine skill had no reveal-by-answer component either. The trigger was a follow-up,
  `heard_about_detail`, after a `heard_about` radio.
- It offered three options.
  1. Always show the follow-up as an optional box.
  2. A one-off Alpine `x-show` reveal wrapped around the two specific question UUIDs, outside
     `form_engine`.
  3. Defer conditionals as a `form_engine` capability.
  It recommended option 3, and shipped option 1 in the illustrative YAML. Its reason for rejecting a
  generic `depends_on` was that it is "a real feature, speculative against a single first use" and
  what "Don't build functionality that is not explicitly requested" argues against.
- `idea.md` (line ~190) and `1. spec.md` (line ~53) carried this forward: "Building conditionals for
  one optional text box is not worth it." The spec's out-of-scope list says each deferred item "is
  buildable the day a form is awkward without it." This feature is that day.
- `research_draft_and_submit_semantics.md`, row 9 "Branching invalidation rule": "Not applicable ...
  Nothing to design against until a form actually branches." The same file says check-your-answers
  and resume machinery "earns its cost on long or branching forms." So that spec built the review page
  and resume path assuming a linear form. Those assumptions are what `idea.md` now has to revisit
  (`resume_page_number`, `furthest_page_reached`, `return=check`).

What this means: the deferral was a cost call against one optional text box. It was never a rejection
of the idea. The trigger the current idea names, the employer-pays application page of required
questions, is a different case. A required question that is always shown is a blocker, not a mild
oddity. The earlier option 1 does not work for it.

### 1.2 Roadmap and sibling specs

- `spec_dd/1. next/roadmap.md` (line ~895) lists `form-engine-branch-logic` as in progress. It says
  the spec shares a per-attempt record with `compliance-form-randomization`, and that "whichever lands
  first designs it for both." Line ~309 flags both specs as touching `form_engine` together with the
  test-organisation cleanup number 9, so test moves there rebase against this work.
- `spec_dd/1. next/multi-step-course-applications/idea.md` (lines ~34, ~141, ~224-234) depends on this
  spec ("ask about previous qualifications and branch on the answer"). It calls branching content and
  says this spec is "already ready to start". There is a downstream consumer waiting.
- `spec_dd/2. in progress/compliance-form-randomization/` has no branch or conditional discussion. Its
  only hit is an unrelated "unlocked options" line about shuffling. The quiz exclusion in `idea.md`
  therefore rests on intent, not on any prior agreement between the two specs.

### 1.3 No code-level traces

Searches of `freedom_ls/form_engine`, the demo content and the rest of `freedom_ls/` for
branch, conditional, skip logic, show-if, required-if, `TODO` and `@claude` found nothing relevant. The
hits were unrelated uses of "branch" and "conditional". There is no stub, TODO or abandoned
experiment to build on or clean up. The `paging.py:57` comment ("A skipped optional question leaves no
answer row behind") means an unanswered optional question, not a skipped-by-logic one. Do not read it
as precedent.

### 1.4 The one workaround that exists

Content authors who need a follow-up today use "if you chose Other or X, who or where, specifically?"
as a question label (`research_question_types_and_validation.md`, around line 381), that is,
"doing by hand what conditional display would". Any rollout should expect existing forms to carry
this wording, and expect authors to want to migrate it.

## 2. Elsewhere

### 2.1 GOV.UK Forms: routing is forward-only and built around one decision per page

- Product page: routes exist for single-select questions (each option can go to a later question, an
  exit page or the end of the form). From "any other type of question" a route can go to a later
  question or the end. The stated purpose is "branches of different questions for people based on
  their answer". The summary page is shown once all questions are answered.
  https://www.forms.service.gov.uk/features
- The wording is "a later question". The page does not state forward-only outright. MoJ Forms, a
  sibling government product, documents branching points whose rules apply top to bottom, with only
  radios and checkboxes supporting branching.
  https://moj-forms.service.justice.gov.uk/branching
- The government design lineage is one-thing-per-page, which GDS argued handles "errors, branches,
  loops and saving progress" better than a long page.
  https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/
- The GOV.UK Design System prototype guidance for the same job puts the simple case, routing by
  answer, first. It defers multiple conditions, user types and skipping questions to a separate
  "routing examples" prototype.
  https://design.tax.service.gov.uk/prototype-guidance/show-different-pages-based-on-answers
- Lesson: a government team with strong accessibility constraints reached routing by pages, not by
  per-question reveal. I could not find a GOV.UK Forms blog post on a "one condition per page" rule
  (the search failed to turn one up, and the docs host `docs.forms.service.gov.uk` was unreachable).
  Do not cite that rule as GOV.UK's without checking it.

### 2.2 Google Forms: section routing, single-choice only

- "Go to section based on answer" works only on Multiple choice and Dropdown question types. Checkboxes,
  short answer and other types cannot route. Routing is per section, so a single question appearing or
  disappearing based on an earlier answer cannot be expressed. The workaround is to put the follow-up
  in its own section. Each answer option has its own destination, defaulting to "Continue to next
  section", and a destination can be "Submit form".
  Google's help: https://support.google.com/docs/answer/141062
  Third-party summaries (not Google): https://www.platoforms.com/blog/google-forms-conditional-logic/ ,
  https://youform.com/google-forms/conditional-logic/
- I could not confirm from these results whether a route can jump backward.
- Lesson: page-only gating, the same shape as `idea.md`, is a shipped product design, and its cost is
  the "needs its own section" pattern. The people who built it also kept the single-choice restriction,
  because a set-valued answer has no single destination. `idea.md`'s membership test for checkbox
  sources goes further than Google did.

### 2.3 Typeform: logic jumps, first-match-wins, no backward jumps to unseen questions

All from community forum posts and moderators, so user-reported, not specification.

- Rules run in the order placed, and the first matching rule applies. Advice from moderators is to put
  the most restrictive rule first.
  https://community.typeform.com/questions/5661
- A jump cannot go backward to a question the respondent has not visited. Doing so "will end the form
  prematurely by showing respondents the submit button".
  https://community.typeform.com/questions/800 ,
  https://community.typeform.com/build-your-typeform-7/backwards-logic-jump-not-working-1008
- A third-party guide tells authors to avoid circular paths and test every path in Preview.
  https://hamsterstack.com/how-to/typeform/create-logic-jumps-branching/
- Lesson: jump-based routing produced rule-order bugs and a half-defined loop semantics, which are the
  "two rules sending one learner to two places" error `idea.md` avoids by choosing gating.

### 2.4 Microsoft Forms: forward-only, consecutive-section branching

Community and third-party sources only. I did not retrieve Microsoft's own support article.

- A Microsoft Q&A answer quotes the official article that branching to a non-adjacent section "might
  break the experience for the respondent", so it is restricted to consecutive questions.
  https://learn.microsoft.com/en-us/answers/questions/5407313/branching-in-microsoft-forms-with-multiple-choice
- Third-party claims, lower reliability: branching only goes forward
  (https://www.wps.com/office-quick-solution/others/how-to-fix-microsoft-forms-branching-to-skip-nonadjacent-sections/)
  and supports one destination per answer choice
  (https://www.wps.com/office-quick-solution/others/how-to-fix-complex-branching-issues-in-microsoft-forms/).
  An Atlassian wiki page claims only one level of branching per question (https://spu.atlassian.net/wiki/x/AYCsJQ),
  which conflicts with Microsoft's own "no limit on the amount of branching".
  https://learn.microsoft.com/en-us/answers/questions/5217875/ms-forms-limits-to-the-no-of-questions-and-branchi
- Lesson: a large vendor chose to restrict rather than define behaviour for complicated cases, and
  its community has been asking about the restrictions ever since.

### 2.5 SurveyMonkey: skip logic is page-level, one rule, forward-only, with documented traps

From SurveyMonkey's own troubleshooting help (retrieved):
https://help.surveymonkey.com/en/create/troubleshooting-skip-logic

- Skip logic only fires on Next, not dynamically on the same page. This is the same server-per-page
  model as FLS. They advise putting the logic question at the end of a page.
- For checkbox and image-choice questions "the system will only refer to the first selection". A
  set-valued answer was squeezed into a single route and the result is a documented gotcha.
- "Skip Logic must always work in a 1:1 ratio." Multiple conditions cannot be combined.
- Self-referencing logic can strand a respondent who is "sent back to the same page and can't move
  forward". A loop shipped as a documented support problem.
- Skipped sections may hold required questions. Authors are told logic "is most likely skipping
  respondents over sections or pages containing required questions". The support article treats
  skipping required questions as a possible author error. `idea.md` makes it the intended behaviour
  via the reachable-set recompute.
- Skip logic "automatically renumbers survey questions based on each respondent's specific logic path".
  Contrast `idea.md`, which keeps `question_number()` stable. Whether renumbering was a good call is
  unclear; the help page does not record complaints.
- From search results, not retrieved: question-level logic overrides page-level logic when both sit on
  one page. This is two mechanisms at two granularities colliding, the Qualtrics pattern
  `research_conditional_logic_models.md` already covers.
  https://help.surveymonkey.com/en/surveymonkey/create/question-skip-logic/

### 2.6 Moodle Feedback: a dependency is a field on the item, with page-break rules

- A dependent item is set up by naming the parent item's Label as "Dependence item" and typing a
  literal into "Dependence value". Users report that separating several values by semicolon did not
  work, so there was no multi-value operator.
  https://moodle.org/mod/forum/discuss.php?d=462894
- Moodle's feedback completion code treats a dependency as broken if the parent no longer exists, and
  a dependency across a page break behaves differently from one on the same page (from a search
  summary of `mod/feedback/classes/completion.php`, not read directly).
  https://git.interlegis.leg.br/ILB/moodle/src/branch/master/mod/feedback/classes/completion.php
- Docs: https://docs.moodle.org/32/en/Feedback_FAQ
- I could not confirm any behaviour of values when the parent item is edited.
- Lesson: this is the closest match to FLS (a text-typed reference plus a literal, in a server-rendered
  form). The failure modes it exhibits are the ones `idea.md` closes at import time: a free-text
  parent reference that can dangle, and a literal typed by hand that matches nothing. Both were
  discovered by users at fill time.

### 2.7 LimeSurvey: relevance equations replaced older conditions

- The Relevance page calls the equation "the successor of conditions and supports much more complex
  conditional logic". A question is shown if the equation is true, hidden otherwise.
  https://www.limesurvey.org/manual/QS:Relevance
- An older manual translation page says a non-relevant question is hidden and its value "NULLed in the
  database", while another example page says an always-hidden equation question still stores its value.
  Both are from search snippets and I could not reconcile them. Whether LimeSurvey clears on hide is
  therefore not established here.
  https://www.limesurvey.org/manual/ExpressionScript_examples
- Lesson: LimeSurvey replaced a structured conditions model with an expression language. That is the
  opposite direction from `idea.md`, and chose power at the cost of an evaluator that has to run in
  both Python and the browser. This pass did not find a post-mortem of the rewrite.

### 2.8 ODK: relevant, and the "when are hidden values cleared" mismatch

- The XForms spec removes data for a non-relevant node on submission. In practice behaviour drifted
  between implementations.
  https://www.github.com/getodk/xforms-spec/issues/153
- The ODK staff reply says both ODK Collect and Enketo clear non-relevant values on submission, but
  "Enketo does use the values during form filling which is a discrepancy we're working to address".
  Enketo's relevance behaviour was being changed to match Collect, with a separate feedback thread.
  Retrieved. https://forum.getodk.org/t/clear-relevant-answers-if-previous-question-is-changed/37839/2
- Search-snippet findings: clearing on hide loses the ability to pre-populate defaults for initially
  non-relevant nodes, and a forum thread says the spec and Collect's behaviour differ.
  https://forum.getodk.org/t/what-happens-when-a-node-is-not-relevant/10534
- Lesson: "keep while filling, clear on submit" is exactly the lifecycle in `idea.md`, and it is the
  one a mature open standard converged on. It still took a cross-implementation fix because two
  engines evaluated the same condition at different moments. `idea.md` has one evaluator, which avoids
  that class of drift, but only if "filtered by the live path" is applied in every reader.

## 3. Lessons for FLS (no implementation plan)

1. The earlier deferral was about cost, not principle. The repo's own rule ("not explicitly requested")
   is satisfied now, since `multi-step-course-applications` depends on this. Existing forms contain
   hand-written "if other, say" labels, so there is a real migration of wording to expect.
2. Every comparator that routes by page ended up restricting the source question type to single-choice
   (Google, GOV.UK, MoJ, Microsoft), or documented a gotcha when it did not (SurveyMonkey checkbox
   "first selection"). `idea.md`'s membership test for checkbox sources is a deliberate departure and
   should be tested hardest.
3. Where a jump model exists, the support burden is rule order, loops and backward jumps (Typeform,
   SurveyMonkey self-reference). Gating on a page avoids these by construction. The cost is in the
   authoring of "needs its own page", and Google Forms users paid it too.
4. Forward-only is near universal (Microsoft, GOV.UK's "later question", SurveyMonkey, Typeform).
   `idea.md`'s earlier-page rule is the same restriction made checkable at import.
5. Skipping required questions is a documented author trap in SurveyMonkey, whereas `idea.md` makes it
   intentional. The risk is not the skip itself but a learner or reviewer reading a missing answer as a
   missing answer. The path record in `idea.md` is what distinguishes the two.
6. Typed-by-hand references and literals fail at fill time in Moodle. The import-time checks in
   `idea.md` (dangling reference, option literal that matches nothing) address the failure that system's
   users found.
7. "Clear on hide" has been unstable in the systems that tried it (ODK engine mismatch, LimeSurvey
   sources that disagree). A single server-side evaluator that every reader shares is the safeguard,
   and each new reader (reports, exports, admin views) is a place the filter can be forgotten.
8. Renumbering questions per path was SurveyMonkey's choice. `idea.md` keeps `question_number()`
   stable. Neither the repo nor the web sources record which one users prefer, so treat the
   path-derived position display as untested.
9. Gaps: no GOV.UK Forms rationale for its routing limits was found, and no LimeSurvey rewrite
   post-mortem. Microsoft's own article was not read. Several Typeform, Microsoft and ODK points rest on
   forums and search snippets.

status: ok
reason: repo history found in simple-application-forms done spec (no git log or commit hashes, no shell); web prior art covers GOV.UK, Google, Typeform, Microsoft, SurveyMonkey, Moodle, LimeSurvey and ODK, with partly forum-sourced evidence flagged
