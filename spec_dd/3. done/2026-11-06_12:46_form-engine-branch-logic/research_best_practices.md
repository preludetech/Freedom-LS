# Best practices for branching pages and questions in multi-page server-rendered forms

Scope: gap areas only. Condition models, evaluation architecture, UX/accessibility, answer lifecycle and authoring syntax are in `research_conditional_logic_models.md`, `research_evaluation_architecture.md`, `research_branching_ux_and_accessibility.md`, `research_answer_lifecycle_and_reporting.md` and `research_authoring_syntax.md`, and are not repeated.

Evidence quality is flagged per finding. Most sources are vendor help pages; where nothing authoritative exists, that is stated.

## 1. Testing branching forms

- Vendor guidance is uniform: every route must be walked, and a survey with N branches needs N test runs, not one. Skip logic "fails silently" on most platforms, so orphaned or unreachable questions only surface through deliberate testing. (https://surveymethods.com/kb/survey-logic-branching/, https://www.casrai.org/guides/skip-logic-branching-questionnaire-design, https://www.koji.so/docs/skip-logic-surveys-guide)
- Path count grows with the number of independent gates (a 6-question survey with 3 skip rules has at least 4 distinct paths), so exhaustive enumeration is feasible for small forms and needs sampling for larger ones. (https://www.koji.so/docs/skip-logic-surveys-guide)
- Gap: no source applies property-based testing to questionnaire routing. The closest literature is symbolic reachability for branch coverage (https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/getmehere-tr.pdf) and targeted property-based testing (https://user.it.uu.se/~hesc0353/avfunpro17/lab-proper/PropEr-6search.html). The following is inference, not an established practice: with Hypothesis, generate an answer vector over the option values, evaluate the path, then assert invariants that must hold for every vector:
  - every page/question reported reachable has a source answered on an earlier page;
  - no required question is both off-path and counted outstanding;
  - the set of questions stored equals the set the path says applies;
  - the denominator equals the max score of the reached questions;
  - every `QuestionOption.value` literal in a condition is reachable from at least one vector (catches "never true" conditions).
- Importer-level static checks (dangling reference, cycle, unmatched literal, never-reachable target) are the cheap analogue of reachability analysis and run in CI over `demo_content`.

## 2. Editing forms that have in-progress or submitted sittings

- Established practice is to version rather than edit a published instrument. A version is a snapshot of the instrument; the version number is recorded in each response; respondents who started on version 2 stay on version 2 after version 3 is published. (https://surveyengine.com/knowledge-base/survey-building/survey-building-methods-versioning/, https://www.qualtrics.com/support/survey-platform/survey-module/survey-publishing-versions/, https://online-help.explorance.com/bluex/articles/modify-a-published-survey-create-versions)
- LifeOmic restricts a new version to adding questions/pages/sections or removing questions, not changing existing ones, and leaves earlier responses intact. (https://platform.docs.lifeomic.com/user-guides/surveys/versioning)
- Known failure modes of in-place edit: moving questions between pages after data collection makes individual responses display wrongly and logic needs rebuilding (Alchemer, https://help.alchemer.com/help/pdfexport/id/5f2ed326ed121cdc148451e5); changing answer choices invalidates collected data, and restoring an old version can resurrect or invalidate data (Qualtrics, https://www.qualtrics.com/support/survey-platform/survey-module/survey-publishing-versions/); SurveyMonkey warns to re-check skip logic when moving questions or pages (https://help.surveymonkey.com/surveymonkey/manage/editing-live-surveys/).
- Gap: no source describes storing a full definition snapshot per response so skip logic can be replayed exactly. Version-number-per-response is the documented norm.

## 3. Audit record of the path: snapshot vs recompute

- No authoritative web source compares the two for forms. The vendors' behaviour above (version stamped on the response) implies that replaying logic against a changed definition is not trusted.
- Reasoning that follows from section 2: recompute is only safe if the definition is immutable for the lifetime of the sitting. If authors can edit conditions on a live form, a recomputed path silently rewrites history, which matches the idea's own argument. A stored record of shown pages/questions is the only form that survives definition edits; a version stamp alone does not, unless definitions are immutable too.
- A hybrid is common in practice (inference): store the path as the record of what was shown and recompute the live path only while the sitting is in progress.

## 4. Required-validation under branching on the server

- Documented trap: required questions hidden inside skipped blocks can block submission, so vendors advise scoping "required" to the path that includes the question. (https://www.koji.so/docs/skip-logic-surveys-guide)
- Multi-select sources can route incorrectly on some platforms, following only the first selected choice. A set-valued source needs explicit membership semantics, not equality on one value. (https://surveymethods.com/kb/survey-logic-branching/)
- GOV.UK: optional skipped questions display as "Not provided" on the review page, which separates "asked, not answered" from "not asked" (not shown at all). (https://design-system.service.gov.uk/patterns/check-answers/)

## 5. Security: trust only server-evaluated reachability

- Mass assignment is a data-binding flaw: client-supplied fields are mapped onto internal objects without checking each is writable. The fix is a server-side allowlist of accepted fields, rejecting or ignoring the rest, with per-field authorisation. Django and DRF serializers express this as explicit field lists. (https://tyk.io/blog/res-owasp-api-security-6-mass-assignment, https://www.pynt.io/learning-hub/owasp-top-10-guide/mass-assignment-vulnerability-how-it-works-6-defensive-measures)
- Mapped onto a branching form: the POST body is an untrusted dictionary; the allowlist is the set of questions the server's path says apply. Anything else in the body (autofill, stale values, forged hidden-flag fields) is dropped. A client-supplied "hidden" flag must never influence required-validation. This is the same posture as the idea; the sources are secondary (blog/vendor), not the OWASP cheat sheet text itself.

## 6. Scoring denominators per respondent

- Covered in depth by `research_answer_lifecycle_and_reporting.md` (prorated vs fixed). Nothing new beyond: when the denominator differs by respondent, reports that assume one max per column are wrong, and the score record should carry its own max so it stays interpretable after the form changes (follows from sections 2 and 3).

## 7. Check-your-answers when a change alters the branch

GOV.UK check-answers pattern (https://design-system.service.gov.uk/patterns/check-answers/):

- Each row has a Change link whose hidden text names what it changes.
- Previously entered values are pre-populated on the edit page.
- After editing, Continue returns the user to the check-answers page rather than making them repeat the rest of the journey.
- If a changed answer means more questions are needed, ask those first, then return to the check-answers page.
- Show only sections relevant to the user (e.g. no non-UK questions once they say they live in the UK).
- Skipped optional questions show "Not provided".
- Implied algorithm (inference): on return-to-check, diff old path against new path; if the new path contains required questions with no answer, send the learner to the first such page, then continue to the next unanswered one, then to the review.
- Loops back: SurveySparrow users report navigation problems after changing earlier responses (https://community.surveysparrow.com/t/problem-with-question-navigation-after-changing-responses/2585), evidence that "change then continue" must be designed rather than assumed.

## Implications for FLS (not a plan)

- Test with both example-based tests per branch (walk each route through `form_fill_page` and `application_form_page`) and a small set of invariants run over generated answer vectors; add importer static checks over `demo_content`.
- Editing a live form is the real hazard. The persisted per-sitting path record is the defence against definition edits; whether it also needs a form version stamp is an open question, and the `compliance-form-randomization` spec should share it.
- The server-computed path is the only allowlist for `save_answers` and required checks; the idea already states this and the security literature supports it.
- Max score should be stored with the sitting's scores so reports remain correct after later edits.
- The `return=check` flow needs "ask newly applicable required questions first, then return", and the review page should distinguish not-asked (omitted) from asked-and-skipped ("Not provided").
- A checkbox source needs explicit membership semantics; the "first selection only" bug in other tools is a cautionary example.

status: ok
reason: gap areas researched; testing/PBT and per-response snapshot practices have thin authoritative sources, flagged as inference
