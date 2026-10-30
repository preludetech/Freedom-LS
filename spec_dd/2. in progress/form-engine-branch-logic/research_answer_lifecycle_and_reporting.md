# Research: answer lifecycle and reporting under branch logic

Topic scope: what happens to `QuestionAnswer` rows and `FormProgress.scores` when a learner's path
through a `Form` changes after they have already answered questions that are no longer on their path.
Covers other systems' behaviour (attributed to them) and closes with FLS-specific recommendations.

## 1. The orphaned-answer problem

When a branch condition flips — "will your employer pay?" from yes back to no — the employer
questions the applicant already answered are no longer reachable. Real systems take one of three
positions: delete on hide, keep-but-mark-inactive, or keep-and-restore-if-they-change-back. None of
the systems researched implement true restore-on-return by default; "the value comes back" is either
absent, or something a survey author has to build themselves.

**REDCap** (Vanderbilt) hides a field whose branching-logic condition goes false, and — outside of
survey mode — prompts the user asking whether they want to *erase* the value of the field being
hidden; the choice is the data-entry person's, not automatic. The `@HIDDEN` action tag is a stronger,
separate mechanism: it hides a field unconditionally (survey page, the data-entry form, and the mobile
app) and keeps it hidden "even if branching logic attempts to make it visible" — i.e. it is not itself
a branching mechanism, it is a permanent-hide flag independent of branch state. REDCap's own guidance
explicitly warns against combining branching logic with its separate "erase data" action tag, because
that combination prompts to erase the value on every evaluation, which is disruptive.
([REDCap Action Tags, University of Alberta](https://help.redcap.ualberta.ca/help-and-faq/action-tags))
Because the prompt is only asked, not automatic, a REDCap field's value is retained by default unless
a data-entry person actively erases it — so "changed my mind twice" in REDCap generally does bring the
old answer back, precisely because nothing deleted it in the first place.

**SurveyJS** makes the delete/retain choice an explicit, named setting, `clearInvisibleValues`, with
four values: `"none"` (never clear — every previously entered value, even for a permanently unreachable
question, rides in the results), `"onComplete"` (the default — invisible values are stripped only at
submission time, so mid-survey branch flips do not erase anything: the value silently survives while
hidden and is deleted only if the question is still hidden when the respondent finishes), `"onHidden"`
(cleared the instant the question itself becomes invisible), and `"onHiddenContainer"` (cleared the
instant the question **or its containing page/panel** becomes invisible — the setting that matters when
a whole page, not just one question, drops off the path).
([SurveyJS Data Model API](https://surveyjs.io/form-library/documentation/api-reference/survey-data-model))
Under `"onHidden"`/`"onHiddenContainer"`, when a question becomes visible again its value comes back
empty (or resets to `defaultValue`, not the applicant's original answer) — SurveyJS's own issue tracker
treats "restore the previous value on re-show" as a *feature request*, not existing behaviour, i.e. the
"changed my mind twice" case loses the original answer under every clearing mode except `"none"`.
([surveyjs/survey-library #2574](https://github.com/surveyjs/survey-library/issues/2574),
[surveyjs/survey-library #2428](https://github.com/surveyjs/survey-library/issues/2428))

**ODK / XLSForm**'s `relevant` column is the closest analogue to the proposed FLS feature (a boolean
expression gating question or group visibility). Its documented behaviour is unambiguous: "In ODK
Collect, when a question is not relevant, its value is treated as blank for all expressions it is used
in, including relevance" — and community/implementation documentation on the KoboToolbox fork of
XLSForm states directly that "If a question is not relevant (it is hidden), then data in that question
will not be submitted." ODK Collect exposes a client setting, `clearIrrelevantImmediately` (default
`true` from Collect 4.41.6), controlling whether the value is wiped the instant relevance flips false
or only at final submission — the same "clear now vs clear at completion" axis SurveyJS names
explicitly. The companion web renderer, Enketo, originally kept irrelevant values live for use in
calculations, which the ODK community treated as a bug relative to Collect's behaviour and later
aligned; Enketo has since removed the separate `clearIrrelevantImmediately` toggle, converging on one
behaviour. ([ODK Form Logic](https://docs.getodk.org/form-logic/),
[enketo/enketo-core #849](https://github.com/enketo/enketo-core/issues/849),
[KoboToolbox: Question options in XLSForm](https://support.kobotoolbox.org/question_options_xls.html))
Because the value is genuinely wiped, ODK's "changed my mind twice" case does **not** restore the
original answer — the applicant must re-enter it once the branch swings back.

**Gravity Forms** goes furthest toward "delete, no trace": fields hidden by conditional logic are
excluded from the submission outright and their values are not saved to the entry at all — described
by its own community documentation as intentional, unchangeable behaviour. A workaround exists (a
plain hidden-type field outside conditional logic, so its value is exempt from this rule), which
implies Gravity Forms treats "hidden by conditional logic" and "hidden by field-type" as two different
mechanisms with two different persistence guarantees.
([Gravity Forms community: hidden fields not submitting data](https://community.gravityforms.com/t/getting-around-conditional-logic-limitations-hidden-fields-not-submitting-data/14404),
[Gravity Forms Docs: Hidden](https://docs.gravityforms.com/hidden/))

**Qualtrics**'s public support documentation does not state its default persistence behaviour for a
value under Display Logic (hide/show) as explicitly as the above vendors do; its own export
documentation, however, implicitly confirms values are not force-deleted — see §2/§6, where Qualtrics
offers to *recode* seen-but-unanswered responses rather than describing branch-hidden fields as always
wiped. ([Qualtrics: Display Logic](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/display-logic/))

**What it cost each choice.** REDCap's "ask, don't auto-delete" costs an interruptive prompt on every
branch flip in data-entry mode (avoided entirely in survey mode, where the value is simply retained
silently). SurveyJS's `onHidden`/`onHiddenContainer` costs the "changed my mind twice" case — a real,
filed complaint from its own users. ODK's unconditional wipe costs the same, but is accepted because
ODK's use case (field data collection, one form, one submission, rarely revisited) tolerates re-entry
better than a multi-page online application does. Gravity Forms' hard exclude-from-submission is the
cheapest to implement and reason about, but is the most surprising to an author who expects "hidden"
to mean merely invisible rather than "never stored."

## 2. "Not asked" vs "asked and skipped"

Survey methodology treats these as materially different missing-data mechanisms, and several standards
give each its own code rather than collapsing both into a blank cell.

- **DDI** (Data Documentation Initiative) conventions distinguish "not applicable" — the respondent was
  routed away from the question by skip/branch logic, historically coded `6`, `66`, `666` — from "no
  answer"/"don't know" — the respondent saw the question and declined or could not answer, historically
  coded `9`, `99`, `999`. The distinction is structural, not incidental: one is a property of the
  instrument's routing, the other a property of the respondent's behaviour.
  ([DDI: Handling of missing values in the QDDT](https://github.com/DASISH/qddt-client/wiki/DDI---Handling-of-missing-values-in-the-QDDT))
- **SDMX** (Statistical Data and Metadata eXchange) likewise carries an observation-status code list
  distinguishing values that are missing because "data cannot exist" / structurally not applicable from
  a generic "missing value" code used when no such breakdown is available — i.e. SDMX also treats
  "could not have applied" as a first-class, separate status from "unknown for another reason."
  ([SDMX CL_OBS_STATUS code list](https://sdmx.org/wp-content/uploads/CL_OBS_STATUS_v2_0_18-6-2014.doc))
- **REDCap**'s Missing Data Codes feature makes this operational rather than merely conceptual: a field
  can carry an explicit, author-defined code such as `NASK, Not Asked` as its literal stored value,
  distinct from a genuinely blank field. Missing codes are queryable in the same logic engine as real
  answers (`isblankormissingcode()`), and — importantly — branching logic that later hides a field
  *does not clear* a missing-data code already stored on it: "if the field has a missing data code
  saved for it, it will hide the field but will not remove the missing data code... allowing a field to
  still be 'blank' and have a missing code even if it is also being hidden by branching logic."
  ([Utah CTSI: Missing Data Codes](https://utahctsi.atlassian.net/wiki/spaces/RC1/pages/1118601267/Missing+Data+Codes),
  [REDCap Action Tags](https://help.redcap.ualberta.ca/help-and-faq/action-tags))
- **Qualtrics** solves the same problem at export time rather than storage time: by default a
  never-shown question and a shown-but-skipped question are both simply blank in the export, but
  Qualtrics offers an explicit option, "Recode seen but unanswered questions as -99," specifically so
  analysts can tell the two apart after the fact — direct documentary evidence that Qualtrics considers
  "shown and blank" and "never shown" to be different things worth distinguishing in the dataset.
  ([Qualtrics: Understanding Your Dataset](https://www.qualtrics.com/support/survey-platform/data-and-analysis-module/data/download-data/understanding-your-dataset/))

Why the distinction matters for research integrity: collapsing both into "blank" silently changes the
denominator any percentage or completion metric is computed against, and it erases the diagnostic value
of "asked and skipped" (which may indicate question wording problems, sensitivity, or a broken branch
condition) versus "never asked" (which indicates a design decision about who the question applies to).

## 3. Required validation

The universal rule across every system researched is: **a hidden required question must not block
submission.** Every vendor implements this either as automatic exemption or as a fixable
misconfiguration:

- **XLSForm/ODK**: "Skip logic conditions take precedence over required settings, meaning that if a
  required question is hidden by skip logic, it is no longer mandatory to answer."
  ([KoboToolbox: Adding required logic in XLSForm](https://support.kobotoolbox.org/required_logic_xls.html))
- **Gravity Forms**: "Required field validation only triggers if fields are displayed; if they are
  hidden by conditional logic, the required field validation is ignored" — stated as the framework's own
  built-in guarantee, not something the form author has to configure.
  ([Gravity Forms community](https://community.gravityforms.com/t/required-field-hidden-by-conditional-logic-not-working/13068))
- **Qualtrics** is the researched system whose failure mode is best documented. Because "Force
  Response" is evaluated server-side against the question's configuration, not against whatever
  hid it, a question hidden purely by client-side JavaScript still triggers "Force Response" — "Hiding
  a question using JS does not mean [it ceases] to exist. Thus, the validation of that question is
  still handled by [the] Qualtrics server," producing the classic un-submittable form: a required field
  invisible to the respondent that nonetheless blocks every submit attempt. Qualtrics's own recommended
  fix is to express the hide condition as first-class Display Logic (which Qualtrics's server does
  honour when evaluating Force Response) rather than JavaScript, or to use custom validation with an
  explicit "is not displayed" check.
  ([Qualtrics Community: force response with display logic](https://community.qualtrics.com/survey-platform-54/how-safe-is-it-to-use-in-page-display-logic-with-force-response-18512))
- This exact failure class is well documented outside survey tools too: a Drupal accessibility bug
  report describes a required field behind an AJAX-hidden state making the whole form silently
  unsubmittable, and a general web-forms write-up describes "a tabbed form that silently refused to
  submit" because a required field sat behind a tab the user never opened — the browser (or server)
  blocked submission on a field the user could not see or reach, with no visible error.
  ([Drupal.org #2571755](https://www.drupal.org/node/2571755),
  ["A tabbed form that silently refused to submit"](https://dev.to/susumun/a-tabbed-form-that-silently-refused-to-submit-required-fields-hidden-behind-another-tab-52e4))

The pattern across all of these: **required is not a static property of a question, it is a property of
(question, current visibility)**, and the two evaluations — "is this visible on this path" and "is this
required" — must be joined and re-evaluated together, every time the path can change, by the same
authority that renders the page.

**Server-side re-evaluation as the authority.** The Qualtrics JS-hiding failure and the Drupal/general
tabbed-form failure are both, at root, the same bug: a client made a visibility decision the server did
not independently agree with, and the server enforced a rule against the state it believed the field
was in rather than the state the user actually saw. The security/integrity argument generalises beyond
UX: if a hidden-required exemption is driven by a client-supplied flag ("this field was hidden, don't
validate it") rather than by the server recomputing the branch condition itself from the stored answers
that decide it, a user can forge that flag to suppress required validation on a field that *should*
have been visible and answerable on their actual path — turning a UX convenience into a way to skip
mandatory questions. The only systems in this research that avoid the failure mode entirely (XLSForm,
Gravity Forms) are the ones where the engine evaluating `relevant`/conditional-logic and the engine
evaluating `required` are the same server-side evaluation, run from the same input (the respondent's
already-stored answers), rather than one trusting a signal the other side supplied.

## 4. Scoring under a variable denominator

None of the general-purpose survey tools researched (SurveyJS, Qualtrics, ODK, REDCap, Gravity Forms)
natively compute a category-value-sum-style aggregate score with a `max_score`; that concern belongs to
scored-instrument methodology rather than survey-platform feature sets, so the evidence here comes from
psychometric scoring guidance for multi-item scales with missing/skipped items, which is the closest
documented analogue to "some questions on a branch never fire."

Two approaches dominate published guidance, and they are genuinely different, not points on one
continuum:

- **Fixed denominator ("percentage of applicable" is not used; every possible point counts).** The
  scale's maximum is the same for everyone regardless of which items they actually saw or answered, so
  a respondent who skipped an item is simply scored 0 on it. This is what today's FLS
  `score_category_value_sum` already does for a currently-unanswered-but-shown question: "An unanswered
  question scores 0 but still contributes its `max_value` to `max_score`." It keeps every learner's
  `max_score` for a given category comparable, but it silently punishes an item a respondent was never
  shown exactly as hard as one they saw and declined — appropriate only when every respondent is
  supposed to see every item.
- **Percentage-of-applicable / prorated scoring.** The denominator is rebuilt from only the items the
  respondent actually encountered, and the raw score is rescaled accordingly. The PROMIS (Patient-
  Reported Outcomes Measurement Information System) scoring manuals are explicit, standards-grade
  guidance for exactly this situation: a domain score requires a minimum completion threshold (commonly
  50% of items in the domain) below which the score is not computed at all, and above that threshold the
  raw score is prorated — `new_raw_score = (raw_score / items_answered) * total_items` — so that two
  respondents who answered different subsets of the same instrument still land on a comparable scale.
  ([PROMIS Meaning and Purpose Scoring Manual](https://www.healthmeasures.net/images/PROMIS/manuals/Scoring_Manuals_/PROMIS_Meaning_and_Purpose_Scoring_Manual.pdf))
  General survey guidance converges on the same shape less formally: "if a person only answers 8 out of
  10 items on a scale... just ignoring the 2 missing items will have a pronounced effect on their
  scores" unless the total is prorated, and skip-logic-induced missingness is recommended to be coded
  as structurally "not applicable" rather than blank precisely so a scoring routine can tell "excluded
  by design" apart from "genuinely missing" before deciding whether/how to prorate.
  ([ResearchGate: cut-off for omitted item responses](https://www.researchgate.net/post/What_is_the_appropriate_cut-off_for_omitted_item_responses_for_a_questionnaire),
  [QuestionPro: Scoring Skip Logic](https://www.questionpro.com/help/scoring-skip-logic.html))

**Which is appropriate when.** A fixed denominator is right when every respondent is meant to answer
every item — branching exists only to skip items that are already known to be irrelevant to *no one*
who reaches that page (e.g. a quiz, which FLS explicitly excludes from this feature's first version).
Percentage-of-applicable is right whenever branching is *itself* meaningful — different respondents are
legitimately being asked different questions because the questions do not apply to them — which is
exactly the FLS use case (an "employer pays" branch, where the employer questions are inapplicable, not
skipped-but-relevant, to a self-funded applicant).

**What a fully-skipped category subtree means for the tree shape.** FLS's `score_category_value_sum`
builds its nested category tree purely by walking `self.form.pages.all()` and every question on every
page — it does not consult which questions were reachable on this sitting's path at all. Concretely,
today, a `FormPage.category` whose entire page is (hypothetically) skipped would still appear in the
tree, contributing 0 to `score` and its full un-shown `max_value` sum to `max_score`, because the
existing loop has no notion of "not applicable" — it only distinguishes answered (nonzero `value`) from
unanswered-but-visible (`value = 0`, `max_value` still counted). There is no existing third state for
"this question was never on this learner's path." Whichever way a branch-aware version resolves this,
it has to decide explicitly, because the current code has no default for it: either the category
disappears (or shows `max_score: 0`) when its entire subtree was inapplicable to this sitting, or it is
counted against every learner at the fixed denominator regardless of path — those are the two
`score_category_value_sum` from §above, applied to a whole subtree instead of one question.

**What breaks if `max_score` varies within a cohort.** Any report or comparison that treats
`FormProgress.scores["max_score"]` (or a category's nested `max_score`) as a constant of the *form*
rather than a property of *this sitting* breaks the moment two learners in the same cohort take
different branches: a cohort-average percentage, a leaderboard, a pass/fail threshold expressed against
a fixed point total, or a report table column header that states "out of N" for the form as a whole, all
silently become wrong or misleading — either comparing apples (a self-funded applicant's smaller,
correct denominator) to oranges (an employer-funded applicant's larger one), or requiring every reader
of the report to already know that `max_score` is per-sitting rather than per-form. `freedom_ls/reports/`
today reads `fp.scores.get("max_score")` (in `gather.py::_score_attempt`) as a single number per
attempt and divides by it (`quiz_percentage()`), so a design that lets `max_score` vary is not free —
the report has to either always show a percentage (never a bare "x / y out of the form's fixed total")
or explicitly caption "out of N" per learner rather than once per column.

## 5. Resume, back-navigation and completion

FLS's `FormProgress.furthest_page_reached` is a single monotonic integer: "The highest-numbered page
this sitting has been shown," moved forward only, never backward
(`record_page_reached`). This model implicitly assumes the pages a sitting is shown are a
contiguous, ever-growing prefix of the form's page list — true today because every sitting sees every
page in order. Branch logic breaks that assumption in a specific way: a sitting that skips a whole page
(the employer-questions page, for a "no" answer) will have a `furthest_page_reached` that is a page
*number* higher than the count of pages it actually saw, because the field counts the highest ordinal
reached, not the count of pages traversed. A progress bar or "page N of M" indicator built naively on
top of `furthest_page_reached` would either be wrong (if M assumes every page is on every path) or
require rebuilding "how many pages *this sitting's path* contains" per sitting rather than reading it
once off the form.

**Whether a "path taken" record is worth persisting** — an explicit, stored realisation of exactly which
pages/questions this sitting actually encountered, as distinct from "the pages the form defines" — is
directly implied by three separate needs already visible in the existing code:

- **Audit/review.** `unanswered_required_in_form` today walks *every* page of `form_progress.form.pages`
  unconditionally to find required-but-unanswered questions, explicitly including "a required question
  on a page the candidate never visited." Once pages can be legitimately unreachable on a given path,
  this function's contract changes: a required employer question on a page the "no" branch never shows
  must stop counting as outstanding, which requires knowing — authoritatively, from data, not by
  re-deriving it from the current in-session state — which pages *were* reachable for this sitting. A
  persisted path record is the cleanest way to answer "was this page ever on this sitting's path" long
  after the fact, without re-running the branch evaluation against possibly-since-edited branch rules.
- **Reproducible reporting.** `freedom_ls/reports/gather.py` and `indexes.py` already lean hard on the
  principle that report data must be derived from batched, frozen queries taken once, not recomputed
  live — the whole module's docstring stresses "no query runs inside a per-learner or per-question
  loop." If "was this question applicable to this sitting" had to be *recomputed* from the branch
  condition and the form's current definition rather than read off a stored fact, a report generated
  after the form's questions or branch rules changed could disagree with what the sitting actually
  experienced — silently rewriting history. A persisted path record pins what happened at the time it
  happened, the same way `FormProgress.compute_quiz_scores()` already documents that "scores are frozen
  at submission and never rescored" for exactly this reason (a stored score can disagree with what the
  same answers would earn under today's rules).
- **Showing the applicant back exactly what they answered.** The check-your-answers page
  (`course_applications/views.py`) is explicitly a GOV.UK-style review step; the whole point of that
  pattern is to show the applicant precisely the questions they were asked and precisely what they
  answered — not a re-evaluation of "what would the branch condition say now." `existing_answers_dict`
  already reads the stored `QuestionAnswer` rows rather than re-deriving from `post_data`, which is the
  same instinct: read what happened, don't recompute it. A stored path record is the natural extension
  of that instinct to "which questions were even asked," not just "what were they answered."

## 6. Reporting and exports

Once different rows (sittings) answer different questions, a flat, column-per-question export
necessarily grows blank cells wherever a question was not on a given row's path — and, per §2, those
blanks are ambiguous between "never asked" and "asked and left blank" unless something distinguishes
them. The two practical shapes documented by the tools themselves:

- **Wide / column-per-question**, the default shape for Qualtrics's and SurveyMonkey's own exports.
  Qualtrics's documentation is explicit that this creates a real interpretive problem once skip logic is
  in play — "When branching means different respondents saw different questions, blank cells in the
  export carry two very different meanings" — and offers a specific, named mitigation: the "Recode seen
  but unanswered questions as -99" export option, which sentinel-codes the "asked and skipped" case so
  it is distinguishable from "never reached" (which stays truly blank).
  ([Qualtrics: Understanding Your Dataset](https://www.qualtrics.com/support/survey-platform/data-and-analysis-module/data/download-data/understanding-your-dataset/))
  SurveyMonkey's export documentation notes the related practical effect of branching on a wide export:
  a skip-logic or randomised survey's export gains extra "Page Order" columns recording which questions
  a given row actually traversed, because the column layout alone no longer tells you that.
  ([SurveyMonkey: Exporting Survey Results](https://help.surveymonkey.com/en/surveymonkey/analyze/exports/))
- **Long format** (one row per (sitting, question) pair rather than one row per sitting) sidesteps the
  blank-cell ambiguity entirely, because a row simply does not exist for a question that was never
  asked, while a row with an empty answer value represents "asked and skipped" — the absent-row-vs-
  present-row distinction the DDI/SDMX missing-value codes (§2) achieve with a sentinel value inside a
  wide table. This is architecturally identical to how FLS already stores answers: `QuestionAnswer` has
  one row per `(form_progress, question)` and an unanswered-but-shown question stores *no row at all*
  ("An unanswered question stores no row at all: `save_answers` deletes any row for a question submitted
  blank... a blank row would count toward the runner's answered tally and hide which questions are
  still outstanding"). FLS's own answer storage is already, in effect, "long format," which is the shape
  every tool researched converges on as the one that survives skip/branch logic without inventing a
  sentinel value.

Practical implication for any export FLS builds off `QuestionAnswer`: a wide, column-per-question
export (e.g. "one row per applicant, one column per question" for a cohort report or CSV download) has
to either accept Qualtrics's blank-cell ambiguity, or explicitly encode the three-way distinction
(never-asked / asked-and-blank / answered) the way Qualtrics's `-99` recode option and REDCap's missing
codes both do — a plain empty cell cannot carry that distinction on its own once branching exists.

## What this suggests for FLS

**Orphan handling.** Delete the orphaned `QuestionAnswer` row when its question drops off the sitting's
current path (matching ODK's `relevant` and Gravity Forms' behaviour), rather than keep-but-mark-
inactive (SurveyJS `"none"`) or REDCap's ask-the-user prompt. Trade-off: this is the simplest to reason
about and keeps `existing_answers_dict`, `unanswered_required_in_form` and `score_category_value_sum`
all reading "does a row exist" as the single source of truth for "is this answered" with no third state
to add — but it means the "changed my mind twice" case genuinely loses the original answer (as it does
in ODK and Gravity Forms), so an applicant who flips a branch condition back and forth has to re-enter
employer details a second time. The alternative (retain-and-restore) would require either soft-deleting
`QuestionAnswer` rows or duplicating SurveyJS's unsolved "restore on re-show" problem — accepting that
cost only makes sense if repeated branch-flipping mid-application is an expected, not edge-case,
interaction.

**Required suppression.** `unanswered_required_on_page` and `unanswered_required_in_form` must both be
re-evaluated against the *current, server-recomputed* set of reachable pages/questions for this
`FormProgress`, never against a client-supplied "this question was hidden" flag — matching the
Qualtrics JS-hiding failure mode and the general argument in §3 that only the server-side branch
evaluation is a trustworthy authority for what was actually reachable. Trade-off: this means the branch
condition has to be evaluated (or the path re-derived) on every submission and on the final
`unanswered_required_in_form` check, not merely read off whatever the browser last rendered — more
server-side work per submission, but it closes exactly the "forge the hidden flag to skip a mandatory
question" hole, and it is the only design that keeps `required` meaning what its docstring already
promises ("catches a required question on a page the candidate never visited").

**`CATEGORY_VALUE_SUM` denominator.** Prefer a per-sitting denominator — a category or the whole form's
`max_score` reflects only the questions actually reachable on *this* sitting's path (the
percentage-of-applicable approach PROMIS documents), over keeping a fixed, form-wide `max_score`
computed by walking every page regardless of reachability (today's behaviour, appropriate only when
every learner necessarily sees every question). Trade-off: this is the only choice that keeps two
learners on different branches comparable at all — a fixed denominator otherwise silently punishes the
self-funded applicant for `max_value` points attached to employer questions they were never eligible to
see — but it means `max_score` becomes a property of the `FormProgress`, not the `Form`, so any report
or UI that currently treats "out of N" as a constant of the form (as `freedom_ls/reports/gather.py`'s
`_score_attempt`/`quiz_percentage` division implicitly does) has to be re-read as per-sitting, and a
`FormPage.category` subtree entirely inapplicable to a sitting should drop out of that sitting's
`scores` tree (or show `max_score: 0`) rather than silently inflate the denominator for a category the
learner was never eligible to be scored on.

**Path record.** Persist an explicit record of which pages/questions a sitting's path actually included
— rather than relying on re-deriving reachability later by re-running the branch condition against the
form's current definition — because `unanswered_required_in_form`'s audit contract, the reports
pipeline's existing "no live recomputation, only frozen batched reads" discipline
(`freedom_ls/reports/gather.py`), and the check-your-answers page's job of showing an applicant exactly
what they were asked all need the same fact: what this sitting's `furthest_page_reached` and its
`QuestionAnswer` rows alone cannot currently reconstruct once pages can be legitimately skipped.
Trade-off: this is additional persisted state and a new invariant to keep in sync with `QuestionAnswer`
and `furthest_page_reached` (which stays a single monotonic integer and cannot itself represent "page 4
was skipped, not merely not yet reached"), but without it, any later change to the branch rule or the
form's page order makes it impossible to say with certainty, after the fact, what a given historical
sitting's path actually was — exactly the drift `compute_quiz_scores` already flags as a real, accepted
risk for scores frozen at submission time.

status: ok
reason: researched via FLS source (models.py, paging.py, queries.py, reports/gather.py, reports/indexes.py) plus REDCap, SurveyJS, ODK/XLSForm, Gravity Forms, Qualtrics, Gravity Forms, DDI/SDMX, PROMIS documentation
