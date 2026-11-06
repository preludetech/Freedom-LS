# Research: known complaints about conditional and branching logic

Scope: what respondents, form authors and people reading results complain about, drawn from vendor
forums, issue trackers and support pages. This extends, and does not repeat, the "Common complaints"
section of `research_branching_ux_and_accessibility.md` (eager or conflicting rules, circular logic,
vendor terminology, same-page limits, mobile keyboard, autofill, jumpy layout) and the orphaned-answer
material in `research_answer_lifecycle_and_reporting.md`.

Method and honesty note. Findings come from web search snippets and a few page fetches. Most forum
threads are anecdotal, so the frequency signal below is "how many independent places say the same
thing", not a measured rate. Where a search found nothing, that is stated under "Gaps" rather than
filled in. Third-party "how to fix" blogs (WPS and similar) are low authority and were not relied on.

Frequency key: **High** = many independent threads or several vendors; **Medium** = a few threads or
one vendor documents it as a known limit; **Low** = a single report.

---

## A. Respondent complaints

### A1. Hidden required field blocks submission (silent or confusing error)  [High]
- Smartsheet users reported hidden required fields still stopped submission; a moderator replied that
  required applies only when the field is displayed.
  <https://community.smartsheet.com/discussion/comment/404328>
- MachForm: a required field shown then hidden again kept blocking submit.
  <https://machform.com/forums/topic/logic-problem>
- Gravity Forms: a field both hidden and required generates a form error on submission.
  <https://community.gravityforms.com/t/required-enabled-in-hidden-field-generates-form-error-on-submission/5888>
- CiviCRM: submit fails **silently** when a required field is hidden by a conditional; client hides the
  field correctly, server-side required validation still fails. This is the exact client/server
  disagreement failure. <https://lab.civicrm.org/dev/core/-/issues/5182>
- OpenSRP FHIR core: same class of bug. <https://github.com/opensrp/fhircore/issues/1593>
- Vendors that solved it say so as a feature: Paperform
  (<https://paperform.co/help/articles/can-i-use-logic-to-show-hide-pages-while-still-making-sure-that-all-questions-are-required>)
  and Jotform (hidden required field auto-set to not required, <https://www.jotform.com/answers/933691>).
- Form.io treats a hidden component as valid by design; Open Forms copied that behaviour.
  <https://github.com/open-formulieren/open-forms/issues/4065>

Respondent-visible symptom: "the form will not submit and I cannot see why." The error names a field the
respondent has never seen. The worst variant is the silent one (CiviCRM) where nothing is shown at all.

### A2. Answers lost or overwritten when the respondent goes back or changes a trigger  [Medium]
- Typeform community: sending respondents backward in the logic path overwrites prior answers, and the
  recommended design is forward-only. <https://community.typeform.com/questions/800> and
  <https://community.typeform.com/build-your-typeform-7/backwards-logic-jump-not-working-1008>
- A Typeform user reported losing the previous question group's answers after returning to the question
  index (same search result set; thread not fetched, single report). Typeform also warns that skip jumps
  can let respondents bypass required questions: <https://community.typeform.com/questions/2053>
- SurveyJS has an opposite design knob, `clearInvisibleValues` (`none`, `onComplete`, `onHidden`,
  `onHiddenContainer`), and its issue history shows the cost of the eager modes: a default-value
  expression stopped recomputing under `onHiddenContainer`.
  <https://github.com/surveyjs/survey-library/issues/7010>,
  original request <https://github.com/surveyjs/survey-library/issues/35>
- Gravity Forms: hidden-field values are not kept; Gravity Wiz sells a snippet to "preserve field value
  on conditional logic hide", which is itself evidence that people want preservation.
  <https://gravitywiz.com/snippet-library/gw-preserve-field-value-on-hide/>

### A3. Progress bar jumps, stalls, or reaches 100% early  [High]
- Qualtrics users: bar moves slowly then leaps; one saw 56% jump to 100% when skipped pages were
  counted. Cause given by other users: default bar counts skipped blocks with branch logic.
  <https://community.qualtrics.com/survey-platform-before-march-2021-56/progress-bar-showing-progress-inaccurately-10038>,
  <https://community.qualtrics.com/custom-code-12/my-progress-bar-is-not-accurate-20891>
- The built-in fix ("Exclude from Progress Bar") did not cure one user whose bar still counted skipped
  pages, and custom JS fixes revert to the default on the next question.
  <https://community.qualtrics.com/custom-code-12/progression-bar-movement-29434>
- Alchemer states the bar is computed over all pages and the only way to avoid the jump is to remove it.
  <https://help.alchemer.com/help/understanding-progress-bar-percentages>
- Useberry feature request thread on the same topic: <https://useberry.nolt.io/320>

### A4. Cannot reach a skipped question again  [Medium]
- Typeform feature request: "let us jump back to a skipped question or a different question branch".
  <https://community.typeform.com/build-your-typeform-7/let-us-jump-back-to-a-skipped-question-or-a-different-question-branch-6842>
- Microsoft Forms branching only goes forward to a later question or the end; users report rules that
  send people to "End of the form" skipping everything after (low-authority source, treat as a lead).
  <https://support.microsoft.com/office/use-branching-logic-in-microsoft-forms-16634fda-eddb-44da-856d-6a8213f0d8bb>

---

## B. Form author complaints

### B1. Cannot test every path  [Medium]
- Qualtrics guidance is to preview the whole survey (not single blocks), pass test values as query
  strings, and repeat with different answers; preview responses are saved and must be deleted from the
  Data tab. Community threads ask how to test show-block and display logic and about previewing blocks
  that appear later in a large skip survey.
  <https://www.qualtrics.com/support/survey-platform/survey-module/more-survey-module/preview-survey/>,
  <https://community.qualtrics.com/survey-platform-54/how-to-test-show-block-display-logic-etc-24610>,
  <https://community.qualtrics.com/survey-platform-54/setting-up-a-large-complex-skip-survey-preview-blocks-that-appear-later-26949>
- A Qualtrics user found the preview did not show a branch until the preview tab was closed and
  restarted. <https://community.qualtrics.com/questions/17604>
- A Qualtrics reporting thread: test responses in a report showed data for questions the respondent was
  skipped past, so the test data was "relatively worthless" (poster later thought it had been fixed).
  <https://community.qualtrics.com/survey-platform-before-march-2021-56/reports-not-acknowledging-skip-logic-637>
- No vendor was found offering exhaustive path enumeration or generated test sittings.

### B2. Logic silently breaks when questions are renamed, moved, deleted or copied  [High]
- LimeSurvey: relevance equations that use the internal SGQA code (not the question code) stop working
  after a question group import or survey copy; a bug report records the Conditions designer writing
  survey-ID-specific variables into the equation, which break on export.
  <https://forums.limesurvey.org/forum/can-i-do-this-with-limesurvey/98758-relevance-equations-not-working-after-question-group-import>,
  <https://bugs.limesurvey.org/view.php?id=8137>
- LimeSurvey: questions containing a relevance equation disappear, traced to stray HTML pasted into the
  equation. <https://forums.limesurvey.org/forum/design-issues/126127-questions-containing-a-relevance-equation-disappear>
- SurveyJS: a `defaultValueExpression` was not updated when a referenced question was renamed (fixed in
  a later release, listed in release notes). <https://surveyjs.io/stay-updated/release-notes/v1.12.53> and the 2.3.6 notes.
- Qualtrics: "invalid display logic" appears when logic points at a later question or a deleted one, and
  the flagged logic is sometimes unrelated to the deletion the author remembers. Deleted questions can be
  restored from the trash and the logic returns with them.
  <https://community.qualtrics.com/survey-platform-54/invalid-display-logic-should-be-valid-28283>,
  <https://community.qualtrics.com/survey-platform-54/deleting-questions-from-an-ongoing-survey-28189>
- Qualtrics, deleted answer choices: a user reported earlier respondents' answers for the deleted choice
  show as blank in summaries. Qualtrics docs and university guides advise hiding a choice with display
  logic rather than deleting it, to keep the label in the data.
  <https://community.qualtrics.com/survey-platform-54/how-to-deactivate-a-multiple-choice-answer-27393>,
  <https://www.usi.edu/media/qfnhn3vk/qualtrics-hide-an-answer-category-or-question-after-a-survey-is-running.pdf>
- Typo'd literals: no thread found describing a literal that silently never matches, but the SurveyMonkey
  and Qualtrics "common errors" pages are the nearest analogue. Treat as unsupported by evidence here.

### B3. Rules cannot be combined, are one-per-option, or are limited to one dependency  [Medium]
- Moodle Feedback allows one dependence item and one dependence value per question; a 4.3.2 forum poster
  could not make a dependent required question work and got no fix.
  <https://moodle.org/mod/forum/discuss.php?d=462894>
- Third-party Moodle Questionnaire plugin moved from one parent answer to multiple conditions over
  versions. <https://moodle.org/plugins/pluginversion.php?id=17153>
- Microsoft Forms: one destination per answer option, no complex per-answer logic.
  <https://techcommunity.microsoft.com/discussions/microsoftforms/multiple-choice-answers-with-branching-per-answer/1276637>
- Typeform: a thread titled "logic breaks when someone chooses multiple options / handling blank answers"
  shows checkbox sources and blank answers as a recurrent trouble spot.
  <https://community.typeform.com/typeform-guides-19/logic-sos-2-help-logic-breaks-when-someone-chooses-multiple-options-handling-blank-answers-2920>

### B4. Performance of large rule sets  [Medium, client-side engines only]
- Jotform: a form with 138 conditions (most hiding 125+ fields) re-checked every condition on every
  field change; another with 84 loaded slowly. Support advice: merge conditions, use a single collapse
  field to control a group. <https://www.jotform.com/answers/1265228-Issues-regarding-form-speed>,
  <https://www.jotform.com/answers/1438355-my-form-is-lagging-slow>
- No Formstack, Gravity Forms or Qualtrics performance thread was surfaced. Server-evaluated,
  POST-per-page engines did not show up in this complaint class at all.

### B5. Terminology and mechanism confusion  [High, partly already covered]
- Qualtrics maintains display logic, skip logic and branch logic as separate mechanisms; the lists of
  "display and skip logic" explainers from university IT desks (for example
  <https://comsupport.fau.edu/kb/articles/qualtrics-display-and-skip-logic>,
  <https://shsu.edu/dept/it@sam/tech-tutorials/qualtrics/skip-logic>) exist because authors mix them up.
  Qualtrics' Survey Checker exists partly to flag conflicts.
  <https://qualtrics.com/support/survey-platform/survey-module/survey-checker/common-user-mistakes>
- Typeform has jump logic but no hide logic, which authors discover only after trying to hide a
  question. <https://community.typeform.com/questions/2345>
- Moodle: core "conditional activities" gate whole activities, Feedback dependencies gate questions;
  the two are documented separately. <https://docs.moodle.org/22/en/Using_Conditional_activities>

---

## C. Results-reader complaints

### C1. Data from hidden fields appears, or fails to appear, in exports  [High, both directions]
- Gravity Forms docs: values of conditionally hidden fields are not saved to the entry and are not
  available to any post-submission process (notifications, exports, feeds). Users then ask for a way to
  keep them. <https://docs.gravityforms.com/enable-conditional-logic/>,
  <https://community.gravityforms.com/t/getting-around-conditional-logic-limitations-hidden-fields-not-submitting-data/14404>,
  <https://community.gravityforms.com/t/conditional-field-data-still-persists-after-edit/7600>
  (title suggests the opposite problem: conditional data persisting after an edit).
- Form.io: hidden components with default values nested in an edit grid were not removed from the
  submission although `clearOnHide` was expected to drop them.
  <https://github.com/formio/formio/issues/1686>
- Drupal Webform: values from conditionally hidden fields still reach the server (issue-tracker context).
  <https://www.drupal.org/node/1840776>
- Qualtrics: respondents who answered "no" still showed data for the follow-ups in a report.
  <https://community.qualtrics.com/survey-platform-before-march-2021-56/reports-not-acknowledging-skip-logic-637>

### C2. A blank cell cannot be told apart: not asked vs asked and skipped  [Medium, structural]
- KoboToolbox treats an unanswered question as an empty string in logic, and a user who re-uploaded a
  form with new skip logic found the stored data changed to obey the new logic, leaving blanks in the
  download. The reader cannot tell which form version produced a blank.
  <https://community.kobotoolbox.org/t/data-not-showing-in-online-forms-but-in-downloads-and-data-table/72214>,
  <https://support.kobotoolbox.org/skip_logic_xls.html>
- A Kobo user got "1" in place of the selected choice for `select_one` questions because of how the
  condition was written, silently corrupting analysis.
  <https://community.kobotoolbox.org/t/select-one-question-returning-all-1s-instead-of-answer-choices/43585>
- No vendor documentation was found that offers a distinct "not asked" marker in exports.

### C3. Percentages and denominators ignore the path  [Medium]
- Same Qualtrics report-versus-skip thread as C1. Alchemer's progress-bar documentation shows the same
  "all pages" denominator design in another area.
  <https://help.alchemer.com/help/understanding-progress-bar-percentages>
- No forum thread was found specifically about prorated scoring denominators; the evidence for this one
  stays in `research_answer_lifecycle_and_reporting.md` section 4.

---

## D. Cross-cutting patterns worth keeping

1. The client and server disagree (A1, CiviCRM, OpenSRP): the dominant cause of "cannot submit" tickets.
2. Eager clearing and lazy keeping both generate tickets (A2, C1): clear on hide loses work, keep on hide
   leaks stale values into exports. Neither default is complaint-free.
3. Identity by name or code is fragile (B2): rename, copy, import and delete all break references, and
   the breakage is discovered late.
4. Totals computed over the full form are wrong for any path-dependent view (A3, C3).
5. Preview tools test one path at a time (B1), so errors surface from live respondents.

---

## E. Which complaints the idea already prevents, and which stay open for FLS

No implementation plan; this is a mapping against `idea.md`.

### Prevented by the design as written
| Complaint | Why it is closed |
| --- | --- |
| A1 Hidden required blocks submit, and client/server disagreement | One server evaluator gates rendering, storage and `unanswered_required_*`; no client rule engine exists. |
| A1 Respondent skipping mandatory questions via a "hidden" flag | The server recomputes the reachable set; client flags are not trusted. |
| A2 Work lost when the trigger is changed back and forth | Off-path rows survive during the sitting. |
| B5 Several mechanisms, conflicting routes | Gating only; no jump or branch graph; one `when` per target. |
| B2 Dangling reference, same-page or later source, cycle, typo'd option value | Rejected at import, with the file and key named. |
| B2 Opaque UUID or positional references | Author-chosen `slug` on `FormQuestion`. |
| B4 Client-side rule re-evaluation cost | No client engine; evaluation happens once per page POST. |
| C1 Stale hidden values leaking into completed records | Off-path rows deleted on submission, readers filter by live path. |
| C3 Path-blind denominators | `max_score` is per sitting. |
| A3 Total that cannot be known | `answered_counts` and position are called out as needing path-derived values. |
| A4 Locked or unreachable links | Skipped pages leave the page nav instead of being greyed. |

### Partly addressed, needs care in the spec
- **A3 Progress.** The idea says the tally "understates" and must change, but does not say what the
  indicator shows when the remaining total depends on answers not yet given. The Qualtrics and Alchemer
  threads show that any denominator that changes mid-sitting reads as a jump. Open.
- **B2 Rename and reorder.** `slug` is stable across reorders, but nothing in the idea says what happens
  when an author renames a `slug` that a `when` references in another file, or deletes or renames a
  `QuestionOption.value` that an already-imported sitting's recorded path depended on. Import-time
  validation catches the new files but not data already collected.
- **C1/C2 Blank versus not asked.** Deleting off-path rows on submit and persisting the path record
  gives the data to tell "not asked" from "asked and left blank", but the idea does not say the
  `freedom_ls/reports/` output or any export must show that distinction. Without it, a missing
  `QuestionAnswer` row reads the same in both cases, as in the Kobo threads.

### Open for FLS
1. **Authors cannot test every path (B1).** Nothing in the idea gives an author a way to see which
   pages and questions a given set of answers produces, or to enumerate paths. Preview-one-path-at-a-time
   is the industry norm and the industry complaint.
2. **Exports and reports distinguishing not-asked from skipped (C2).** Open, as above.
3. **Form edited after sittings exist (B2, C2).** Kobo users saw old data change to match new logic.
   The persisted path record protects completed sittings, but in-progress sittings are re-evaluated
   against the edited condition. What an in-progress learner sees when the authored form changes under
   them is not decided.
4. **Checkbox sources (B3).** The idea names membership testing, but a single `equals`-style operator
   set will meet the "logic breaks with multiple options / blank answers" class of problem. Which
   operators exist and what a blank source answer evaluates to are not specified.
5. **Same-page "Other, please specify" (A4 cousin).** The idea concedes this costs a page break; the
   complaint pattern is real but accepted, not solved.
6. **Resume landing (A2/A4).** Idea lists it as to be revisited; the Typeform back/overwrite threads
   show respondents hit this, so it remains open until specified.
7. **Author-facing diagnostics for a condition that is valid but never true in practice**, such as a
   source question that is itself usually skipped. Import checks cannot see this. No evidence was found
   of a vendor that catches it; it is a plausible gap rather than a documented complaint.

---

## Gaps in this research
- Google Forms back-button answer retention, GOV.UK Forms feedback and SurveyMonkey scoring-with-skip
  produced no usable thread in the searches run; absence here is not evidence they have no complaints.
- No LimeSurvey thread on exports of hidden-question answers was found.
- Frequency signals are counts of independent reports found, not prevalence.

status: ok
reason: five audience-classified complaint groups with URLs, mapped against the idea as prevented, partly addressed and open; some requested vendors had no thread found and are listed under Gaps
