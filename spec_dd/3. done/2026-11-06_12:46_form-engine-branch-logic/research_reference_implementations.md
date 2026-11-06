# Reference implementations: page- and question-level conditional display

Scope: code-level behaviour of open-source implementations. The conceptual survey of Qualtrics, SurveyJS,
REDCap, XLSForm/ODK, Gravity Forms, GOV.UK, Moodle and QTI is in the sibling `research_*.md` files and is
not repeated. Method caveat: sources were read through page fetches of raw GitHub files and docs; where a
fetch did not expose the code (noted per item) the claim is marked **unverified** rather than guessed.

## 1. GOV.UK Forms runner (alphagov/forms-runner, Ruby/Rails, server-rendered, POST-per-page)

The closest architectural match to FLS: one page per request, state held server-side, no client rule engine.

- **Data shape of a condition.** A routing `Condition` wraps a form-document condition with `check_page_id`
  (the page whose answer is tested), `goto_page_id` (nullable), `answer_value`, plus `skip_to_end` and
  exit-page fields. A blank `answer_value` marks the default branch. Match is plain string equality, with a
  special-case sentinel for "none of the above". Source:
  https://github.com/alphagov/forms-runner/blob/main/app/models/condition.rb
- **Important contrast with FLS.** GOV.UK conditions are *routes on the source page* ("if answer is X, go to
  page P"), not gates on the target. Only selection (radio/checkbox-style) questions can be sources. Routing
  is a graph, which is the model the FLS idea deliberately rejects.
- **Where evaluated.** `Step#next_step_slug_after_routing`: no matching condition goes to `next_step_slug`;
  an exit-page match returns nil; skip-to-end goes to Check Your Answers; otherwise `goto_page_id`.
  https://github.com/alphagov/forms-runner/blob/main/app/models/step.rb
- **Computing the reachable path.** `Flow::Journey#completed_steps` is
  `each_step_with_routing.take_while { |step| step_is_completed?(step) }`. The walker starts at `:_start`,
  loads the stored answer into each step, asks for the next slug after routing, and stops at an already
  visited slug (loop guard, comment "Prevent infinite loop if a route goes back on itself") or at the
  Check Your Answers marker. The path is therefore *derived on every request from stored answers*, not
  persisted.
  https://github.com/alphagov/forms-runner/blob/main/app/lib/flow/journey.rb
- **Off-path answers.** They are left in the answer store but never read: the code comment says completed
  steps are generated first "to load answers only for steps that will be visited taking routing into
  account". Steps skipped by routing never have their answers loaded, so they cannot reach check-your-answers,
  email, or submission. No deletion step was found in the files read (the store itself, `Store::DatabaseAnswerStore`,
  was not read: **unverified** whether anything prunes it at submit).
- **Required validation.** `Step#skipped?` is "optional and unanswered". Because only on-path steps are
  walked, an off-path required question cannot block; there is no separate "hidden" flag for the client to
  forge.
- **Progress/resume.** `Journey#can_visit?(slug)` is true only for a completed step or the single next step,
  so a learner can revisit completed pages but never jump ahead by URL. `next_step_slug` is the last completed
  step's routed next step, which is the resume point and is always on-path by construction. `completed_steps`
  stops at the first unanswered step (contiguous run), so a changed earlier answer automatically truncates
  the trusted prefix and sends the user to the first newly-needed page. There is no "N of M" total.
- **Check your answers after a changed route.** Check Your Answers is a terminal step in the walk; a changed
  answer shortens or lengthens `completed_steps`, and the next step is recomputed, which is the behaviour the
  FLS idea wants for `return=check`.
- **Test approach.** Not read at file level. The README names RSpec in `spec/`
  (https://github.com/alphagov/forms-runner). **Unverified** beyond that.

## 2. django-formtools WizardView `condition_dict` (the Django-native precedent)

https://github.com/jazzband/django-formtools/blob/master/formtools/wizard/views.py

- **Data shape.** `condition_dict = {step_name: bool | callable(wizard)}`; missing keys default to included.
  The callable gets the wizard and typically reads `wizard.get_cleaned_data_for_step("earlier_step")`.
  It is arbitrary Python, i.e. the code-level equivalent of an expression engine, with no authoring-time
  validation.
- **Where evaluated.** `get_form_list()` builds the active ordered step list by filtering on each
  condition; the result is cached and the cache is cleared after every valid step POST (the answer may change
  conditions). A recursion guard returns the unfiltered list if a condition itself calls `get_form_list`.
  All navigation (`get_next_step`, `get_prev_step`, `get_step_index`) uses the filtered list; if the current
  step is no longer active, `get_next_step` falls back to the first step.
- **Off-path answers.** Step data is stored per step in the storage backend (session/cookie). Nothing
  deletes the data of a step that becomes inactive; it simply stops being iterated (inferred from the code,
  not documented). This is the same "keep while in progress, ignore on read" posture the FLS idea picks, but
  without any submit-time cleanup because `storage.reset()` drops everything at the end.
- **Required validation / submit.** `render_done` re-validates *every step in the current `get_form_list()`*
  from stored data, so an inactive step's required fields cannot block, and a step whose data no longer
  validates is re-presented (`render_revalidation_failure`). This is the "recompute the reachable set at
  submit, trust nothing rendered" rule in 20 lines.
- **Progress/resume.** Position is `storage.current_step`; because the list is recomputed, the step index
  and "step N of M" shift as conditions flip. Wizard has no path persistence.
- **Test approach.** The upstream wizard tests use fixed four-step flows and do not exercise
  `condition_dict` (checked `tests/wizard/wizardtests/tests.py` and `namedwizardtests/tests.py`): the
  conditional path is under-tested upstream. Lesson: the revalidation-on-done behaviour is the part worth
  testing in FLS.

## 3. Open Forms (open-formulieren/open-forms, Django + DRF, JS SDK)

Closest Django codebase with *persisted* applicability, but it is a SPA-style client with backend logic
calls, not POST-per-page.

- **Data shape.** Backend logic rules are `trigger` (a JSON Logic expression evaluated by a Python JSON Logic
  implementation) plus `actions` (set variable, mark step not-applicable / applicable, property changes such
  as hidden). Docs:
  https://github.com/open-formulieren/open-forms/blob/2.3.7/docs/developers/sdk/logic.rst
- **Two evaluation tiers.** Component-level rules run in the browser, are single-step, and can override
  backend results. Backend rules run on the server, can read multiple steps, and are the only ones that can
  toggle step applicability. The docs themselves warn that mixing both can make focus jump unexpectedly.
  This is the duplicated-engine cost in a shipping product.
- **Applicability is per-submission state, not recomputed from scratch.**
  `SubmissionStep.is_applicable` returns a per-submission override `_is_applicable` if set, else the form
  step's default. https://github.com/open-formulieren/open-forms/blob/master/src/openforms/submissions/models/submission_step.py
  `StepApplicableAction.apply()` sets that flag on the loaded submission execution state and does not touch
  stored data:
  https://github.com/open-formulieren/open-forms/blob/master/src/openforms/submissions/logic/actions.py
- **Where evaluated / ordering.** `iter_evaluate_rules` runs rules sequentially over the variable data;
  mutations are applied immediately so later rules see them. `get_current_step` is "the step after the last
  completed", capped at the last, explicitly *before* logic is evaluated (a step that later becomes
  not-applicable can still be returned, a documented gap).
  https://github.com/open-formulieren/open-forms/blob/master/src/openforms/submissions/logic/rules.py
- **Off-path answers (clear-on-hide).** Hiding a component with `clearOnHide` resets the value during the
  logic check, and a second copy of the data (`data_for_visible_state`) is kept so the value can be restored
  if visibility flips back. The 3.5.x changelog notes a breaking change planned for 4.0 in this area, and a
  3.5.4 fix for "cosign required" validation ignoring whether a step was applicable, i.e. the hidden-required
  class of bug appeared in a mature codebase:
  https://open-forms.readthedocs.io/en/3.5.7/changelog.html
  A forgiving pattern worth noting: they keep a shadow copy to make flip-flop lossless, versus FLS's "keep
  the rows" approach.
- **Progress/resume.** Applicable steps drive the step list; a non-applicable step is removed from the
  navigation. Not verified at file level.
- **Test approach.** Not read. **Unverified.**

## 4. pyxform + ODK/Enketo (XLSForm `relevant`)

Concept covered in `research_conditional_logic_models.md`; code-level points only.

- **Data shape.** `relevant` column is an XPath expression compiled by pyxform into an XForms `bind`
  attribute; references are `${name}` rewritten to node paths. https://github.com/XLSForm/pyxform
- **Off-path data.** The XForms spec: "When `false()` the data node (and its descendants) are removed from
  the primary instance on submission." The spec does not say whether `required` on a non-relevant node is
  waived. https://getodk.github.io/xforms-spec/ Practically the engines (Collect, Enketo) skip required
  checks on non-relevant nodes, but that was not verified in `enketo-core` source (fetch returned 404).
- **Consequence for editors (KoboToolbox).** A community answer notes that setting a question's relevance to
  false clears its stored value on the next save, including edits through the server-side modal:
  https://community.kobotoolbox.org/t/hiding-a-question-from-within-a-deployed-survey/37519
  Hidden = value discarded is again the coupling the FLS idea avoids.
- **Test approach.** pyxform's `PyxformTestCase` with `xml__xpath_match` asserts on the generated XForm
  (README above). The tested artefact is the compiled rule, not runtime behaviour: a useful model for
  asserting importer output in FLS.

## 5. LimeSurvey (Expression Manager)

- **Data shape.** A relevance equation string per question or group; `.NAOK` and `relevanceStatus`
  variants control how a referenced irrelevant question reads.
- **Off-path answers.** Default `deletenonvalues = 1`: answers to irrelevant questions are NULLed in the
  database. Setting it to 0 keeps them, but forum answers say hidden-question values are still treated as
  empty in other equations. Manual:
  https://www.limesurvey.org/manual/Optional_settings ; forum thread
  https://forums.limesurvey.org/forum/can-i-do-this-with-limesurvey/124510-irrelevant-group-not-to-clear-data-possible
- **Failure modes (evidence for the "silent never-true / wrongly cleared" hazard).**
  - Answers not saved when the referencing equation used a bare variable whose source was itself irrelevant
    (fixed by `.NAOK`): https://forums.limesurvey.org/forum/design-issues/100178-use-of-naok
  - A question visible and answerable but never saved because of a `relevanceStatus == 0` comparison:
    https://forums.limesurvey.org/forum/can-i-do-this-with-limesurvey/119540-using-relevancestatus-in-relevance-equations-of-further-questions
  - Mass answer loss after editing a group's relevance (closed as not reproducible):
    https://bugs.limesurvey.org/view.php?id=15522
  - Equation-type questions still evaluated while irrelevant: https://bugs.limesurvey.org/view.php?id=8647
- Required handling and test approach were not read at code level. **Unverified.**

## 6. Wagtail form builder packages (Django)

Wagtail core has no conditional display for form builder fields; the long-open request is
https://github.com/wagtail/wagtail/issues/2172 . Third-party options found: Wagtail Advanced Form Builder
(https://wagtail-advanced-form-builder.readthedocs.io/, conditional visibility and validation, field-to-field
rules) and `wagtail-form-mixins` (https://pypi.org/project/wagtail-form-mixins). Both are single-page forms
whose reveal is client-side, so they are weak references for multi-page server path computation. Internals
not read: **unverified**.

## 7. Not covered

Not reached: django-survey / django-forms-builder variants, MoJ / DfE builders, Formbricks (a TypeScript
product, not Django), and the actual LimeSurvey PHP and Enketo JS sources. Findings above should not be
read as covering them.

## 8. Cross-cutting comparison

| System | Condition lives on | Shape | Evaluated | Off-path answers | Required |
| --- | --- | --- | --- | --- | --- |
| GOV.UK runner | Source page (route) | Structured: check page, answer, goto | Server, per request, walk from start | Kept, never read | Only on-path steps walked |
| formtools | Target step | Python callable | Server, recomputed each POST | Kept, ignored | Revalidate active steps at done |
| Open Forms | Rules (trigger + actions) | JSON Logic | Server and client tiers | Cleared if `clearOnHide`, shadow copy to restore | Needed a fix for applicability |
| ODK / Kobo | Target question | XPath string | Client engine | Dropped on submit; cleared on edit | Spec silent |
| LimeSurvey | Target question | Expression string | Server EM + JS | NULLed by default | Quirks around NAOK |

## 9. What the strongest patterns imply for FLS

- **Derive the path by walking, from stored answers, on every request.** GOV.UK and formtools both do this
  and it is the only pattern that kept the page, the resume point, required-validation and check-your-answers
  from disagreeing. The earlier-page rule makes the walk a single forward pass with no loop guard needed
  (GOV.UK needs one because its routes can go backwards; gating on earlier sources cannot).
- **Keep off-path rows and filter every reader by the live path.** GOV.UK and formtools do exactly this;
  the systems that clear on hide (LimeSurvey, Kobo, Open Forms' `clearOnHide`) are the ones with the
  data-loss bug reports above, and Open Forms needed a shadow copy to patch flip-flop. Neither reference
  system deletes at submit, so the FLS submit-time deletion is its own decision with no code precedent here.
- **Revalidate against the recomputed path at completion.** formtools `render_done` is the compact
  prototype: iterate only active steps, re-present the first failing one.
- **Bound navigation by the path.** GOV.UK `can_visit?` (completed or the single next step) prevents URL
  jumping onto an inapplicable page, which addresses the resume / `furthest_page_reached` concern directly.
- **Gate on the target, with structured data, was not the norm in the Django/GOV.UK references.** formtools
  uses callables (unvalidated), GOV.UK uses source-side routes. FLS's target-side structured `when` has no
  direct open-source twin; the nearest validation precedent is pyxform's compile-time checks.
- **A duplicated engine is a shipping cost.** Open Forms documents focus jumping and a backend/frontend
  precedence rule; this supports server-only evaluation.
- **Persisting the path is unusual.** None of GOV.UK, formtools, or the surveyed Open Forms files persist a
  per-sitting path record; they recompute. A persisted path (idea.md) is therefore a deliberate departure
  justified by audit and the shared randomization record, not by precedent.
- **Test approach to borrow.** Assert the compiled/imported condition shape (pyxform style), and test the
  completion revalidation and flip-flop cases that formtools' own suite omits.

status: ok
reason: Code-level survey done for GOV.UK runner, formtools, Open Forms, pyxform/ODK, LimeSurvey; several sources (Enketo, LimeSurvey code, test suites, Wagtail internals) unverified and flagged.
