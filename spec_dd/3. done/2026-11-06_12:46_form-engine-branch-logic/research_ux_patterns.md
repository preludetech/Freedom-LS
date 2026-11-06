# Research: UX patterns for conditional pages and questions (gaps beyond the branching/a11y note)

Scope: the five gaps `research_branching_ux_and_accessibility.md` does not cover: (1) progress and
page-jump under variable paths, (2) check-your-answers when an edit changes the route, (3) resume,
(4) how review and educator/admin views show "not asked" questions, (5) author-facing UX. Progressive
disclosure, WCAG, disabled state, orientation basics and back-navigation are in that note and are not
repeated. Terms follow the idea file: `condition`, `FormPage`, `FormQuestion`, path, sitting.

Honesty note: several searches returned thin or no primary documentation. Where a topic had no
authoritative source, that is said, rather than filled with inference dressed as a finding.

---

## 1. FLS screens these findings map to

| Screen | Template / code | What it shows today |
|---|---|---|
| Course-player form page (`form_fill_page`) | `freedom_ls/learner_interface/templates/learner_interface/course_form_page.html` | Top bar "`{{ answered_count }}` of `{{ total_question_count }}` answered" (`data-testid="answered-summary"`); strip "Page N of `total_pages`" (`data-testid="page-indicator"`) plus a `widthratio` progress bar; page dots (`exam-page-dots` partial) from `page_links`, locked pages are a non-link `<span aria-label="Page N (not yet accessible)">`; sr-only `<h1>` and `aria-live` region both say "Page N of M"; submit dialog "Answered / Total questions" tiles. |
| Application-form page (`application_form_page`) | `freedom_ls/course_applications/templates/course_applications/form_page.html` | `<nav aria-label="Application pages">` of `<c-form-page-link>` numbered links; "Next" / "Previous"; in `return=check` mode the buttons become "Save and return to your answers" and "Back to your answers". No "N of M" text at all. |
| Check your answers | `.../course_applications/check_your_answers.html`, view `application_check_answers` | One card per page, titled `Page N` if the page has no title, "Edit" + sr-only page title; each row shows the answer or muted "Not answered". Submit runs `unanswered_required_in_form`; error is a callout "Question 5 needs an answer ..." with no link to the question or its page. |
| Admin response view | `freedom_ls/form_engine/templates/admin/form_engine/_answers.html` | Table grouped by page; "Not answered" for a question with no row. Same word is used for every cause. |
| Resume | `course_applications/views.py::_resume_url`, `form_engine/paging.py::resume_page_number` | max of current page, furthest answered page, `furthest_page_reached`, clamped to page count. |
| Edit-from-review | `RETURN_TO_CHECK = "check"` in `application_form_page` | On an accepted POST with `?return=check`, always redirects to check answers. Never to the next page. |

The two runners already differ: the course player exposes "Page N of M" in four places (visible
text, bar width, sr-only `<h1>`, `aria-live`), the application shell exposes none. Whatever the
variable-path decision is, the course player has more to change.

---

## 2. Progress indicators and page-jump under variable paths

### What the design systems actually say

- **GOV.UK question pages**: test without a progress indicator first; add a "simple step or question
  indicator" only if people still struggle; "only include the total number of questions if you can do
  so reliably". The same page warns against an indicator that lists all questions, lets users navigate
  to previous questions and shows the current one: such indicators are "often not noticed" and "make it
  hard to handle conditional sections". It cites the Carer's Allowance team removing a 12-step
  indicator with no negative effect on completion rates or times.
  <https://design-system.service.gov.uk/patterns/question-pages/>
  (The existing research note cites this page for reliability of the total; the **"hard to handle
  conditional sections"** warning against an all-steps navigator is new, and bears directly on the
  FLS page dots and numbered page links.)
- **Australian Government Agriculture Design System**: indicators suit forms "with a known number of
  steps"; "avoid adding or removing pages to a multi-step form where a progress indicator is used as
  this can confuse and mislead users. Consider another approach if the number of steps might change
  due to user input."
  <https://design-system.agriculture.gov.au/components/progress-indicator>
- **NSW Design System community**: same ordering, improve question order/type/number first, then add a
  simple step or question indicator if needed.
  <https://community.designsystem.nsw.gov.au/t/progress-indicators/669>
- **Alberta design system**: label "Question X of Y" for single-question pages and "Step X of Y" when
  grouping related questions into sections.
  <https://design.alberta.ca/examples/show-a-simple-progress-indicator-on-a-question-page-with-multiple-questions>
- **GOV.UK design notes (2015)**: recommends "a simple step indicator (e.g. Question 3 of 5)" for
  one-thing-per-page.
  <https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/>

### Patterns that fall out of those sources

1. **Drop the denominator, keep the position/done count.** "N answered" with no "of M" never lies when
   the path shifts. GOV.UK/Agriculture both treat a changing total as the failure; neither requires a
   total. Variants: "Page 3" only; "Section: Employer details"; or a numerator-only tally.
2. **Count the denominator from the live path, and say so once.** The reliable-total condition is met
   if the total is recomputed from the current path at render time. The risk is the number moving
   between pages (a total of 20 becomes 15 after one answer). Design systems treat that jump as the
   thing to avoid, so a recomputed total is acceptable only with a form that rarely flips.
3. **Show the total as an upper bound or range** is not recommended by any source found; no pattern
   evidence. Not offered.
4. **Section-level indicator ("Step 2 of 4") fails the same way** if sections are the conditional
   unit, which in FLS they are (`FormPage` is the gated unit). A skipped page changes the step count.

### Page-jump / section navigation that omits skipped pages

- No design system found documents omitting a skipped step from an all-steps nav as a named pattern.
  GOV.UK's stance is the stronger form of it: the all-steps nav is discouraged for conditional
  sections at all (see above).
- GOV.UK's *step-by-step navigation* (a different pattern, for multi-service journeys rather than
  forms) lists steps up front as links to content. Not form fields.
  <https://design-system.service.gov.uk/patterns/step-by-step-navigation/>
- **Consequence for numbering**: if a nav omits skipped pages, the visible numbers must be renumbered
  (1,2,4 becoming 1,2,3) or the page labels dropped, otherwise a gap looks like a bug. The FLS dots and
  `c-form-page-link` take `page.number` from `enumerate(pages)`. The existing note's rule is to keep
  `question_number()` as a stable identity and add a separate path-derived position; the same split
  applies to page numbers: the URL number (`/page/<n>/`) is identity, the label is position. Both
  runners route by index into `form.pages.all()`, so a URL number that no longer appears in the nav can
  still be hit by a stale bookmark or the browser back button.
- **Titles instead of numbers** (the application shell's check-your-answers already does
  `{{ section.title }}` falling back to `Page N`) survive skips with no renumbering problem. Pages with
  no title would show a fabricated "Page N" that shifts.

### Unreached vs skipped in the nav

The idea file already omits skipped pages. A second distinction that no source treats explicitly but
that falls out of the data: a page *ahead* of the learner whose condition is **not yet decidable**
(its source is on an earlier page not yet answered) versus a page **decided false**. For the former,
the existing `is_accessible=False` dot is the honest rendering (we do not know yet); for the latter,
omission. A nav that omits undecidable pages would silently shrink, then grow when the trigger is
answered, which is the "jumpy" total again. This is design inference, not a cited finding.

---

## 3. Check-your-answers when an edit changes the route

### What the sources say

- **GOV.UK Design System, Check answers pattern** (fetched this session): a "Change" link next to each
  section, each with hidden text describing what it changes; "If a change means more questions are
  needed, ask them before the user returns to the check answers page"; "only show sections that are
  relevant to users"; an optional question the user skipped is displayed as **"Not provided"** in the
  worked example (Customer reference).
  <https://design-system.service.gov.uk/patterns/check-answers/>
- **GOV.UK Prototype Kit**: branching is hand-written route code that redirects on the submitted
  answer; the Change link only works once its href points at the question page; the saved answer does
  not pre-fill unless you wire the `values`. In other words GOV.UK ships **no built-in** engine for
  the "edit, re-route, return" loop; each service builds it.
  <https://prototype-kit.service.gov.uk/make-first-prototype/let-user-change-answers/>
- **MoJ Form Builder**: authors may "point all your branches to the same page (for example, the check
  answers page)", i.e. the review page is the merge point of a branch. Also: pages that lose their
  route become "unconnected, hidden from users" and are listed in a separate section.
  <http://formbuilder-product-page.apps.live.cloud-platform.service.justice.gov.uk/branching/>
- **GOV.UK Forms** features page: routes send people to a later question, an exit page, or the end of
  the form; it does not describe change-link behaviour.
  <https://www.forms.service.gov.uk/features>
- No source found describes the data side (what happens to answers when the loop re-routes). The idea
  file decides that.

### The edit loop, as a pattern

The pattern GOV.UK describes is a **detour**: Change -> edited page -> (zero or more newly
applicable pages, in order) -> back to review. Design decisions the sources leave open and FLS has to
make:

1. **What triggers the detour.** Compare the applicable set before and after the save; if it grew
   (new unanswered applicable pages or questions), walk the learner through the *newly applicable and
   still-unanswered* ones; if it only shrank, return straight to review with the removed section gone.
   GOV.UK's wording covers growth ("more questions are needed") and says nothing of shrinkage.
2. **The detour's boundaries** should be the newly applicable *pages* (the POST-per-page unit), not
   questions; with the earlier-page rule a newly applicable question can only sit on a page the
   learner has not yet seen or has already answered a sibling on.
3. **Return marker vs queue.** The current `?return=check` is a single bit carried in the query string
   and "survives both the save and a 422 re-render". A detour needs either a derived rule ("after a
   save in return mode, go to the first applicable unanswered page after this one, else review") or a
   queue. A derived rule needs no extra state, which fits the server-rendered shape; no source compared
   the two.
4. **Button copy during the detour.** FLS's in-repo copy ("Save and return to your answers" / "Back to
   your answers") is wrong on a detour page that does *not* return to review. Expect it to change per
   page (Continue vs Save and return). GOV.UK does not specify the copy.
5. **Back from a detour page.** "Back to your answers" on a newly applicable page would abandon
   mid-detour; the review page must then show the new section as "not answered" and block submit via
   `unanswered_required_in_form`, which already works. The failure to avoid is review showing a section
   that *looks* complete when it is an unvisited newly applicable one with no required questions.
6. **Where a required error lands.** Current error "Question 5 needs an answer before you can
   continue." on check answers names a number but links nowhere. Under conditions the number is a
   *stable ordinal* (per the idea), so it can refer to a question the review page does not display. GOV.UK
   validation guidance expects an error summary whose items link to the field; the validation pattern
   states the general rule: <https://design-system.service.gov.uk/patterns/validation/>.
7. **"Change" link hidden text.** Already done in FLS (`Edit<span class="sr-only"> {{ title }}</span>`),
   but when `section.title` is empty the sr-only text is `page N`, which shifts if numbering is
   path-derived.

---

## 4. Resume landing on the right page

- **GOV.UK Forms**: save-and-return is listed under "forthcoming features" (so not shipped), and the
  features page says nothing on skipped/conditional pages at resume.
  <https://forms.service.gov.uk/forthcoming-features>, <https://www.forms.service.gov.uk/features>
- **MoJ Forms save-for-later**: emailed link plus security question to return "to where they left
  off"; the post is silent on conditional questions.
  <https://mojdigital.blog.gov.uk/2023/10/26/balancing-security-and-usability-to-add-save-for-later-to-moj-forms/>
- **Canada.ca alpha, "Enabling people to return to a partially filled form"**: generic save-and-return
  guidance.
  <https://articles.alpha.canada.ca/forms-formulaires/return-to-partially-filled-form/>
- **Jotform user report**: a resume link taking the user to the first question every time, as a known
  frustration rather than a design.
  <https://jotform.com/answers/1355730-is-there-a-way-to-save-and-come-back-later-to-complete>

Search result: **no authoritative source documents resume semantics under conditional routing.** What
exists is inference from the two behaviours in general use:

| Resume rule | Used by (evidence) | Failure under conditions |
|---|---|---|
| Furthest page ever reached | FLS today (`furthest_page_reached`); generic wizards | Lands on a page the current answers have since skipped. |
| First unanswered required question on the live path | Not evidenced in a named product here | Skips optional pages the learner never opened; can fire a long way back and feel like a regression. |
| First page on the live path *after the furthest reached one that is still applicable* | Not evidenced | Requires "applicable" evaluation at resume time; the idea file already requires this. |
| Always the first page | Jotform report | Safe but discards position. |

The load-bearing UX point the idea file already holds: a resume must not land on a skipped page.
The additional UX question it leaves open: when the learner's furthest-reached page has since become
inapplicable, land on the nearest *earlier* applicable page (where they last were) or the nearest
*later* one (what they would have seen next)? Neither is sourced. Landing earlier is conservative (the
learner re-sees their trigger answer); landing later may jump past an unanswered required question that
only the final check catches. The current `furthest` is also the ceiling for page-jump accessibility
(`page_accessibility_limit`), so the resume rule and the nav ceiling must agree or the dots show a
reachable page the resume skips.

---

## 5. How review and admin/educator views show "not asked"

### What other products do

- **GOV.UK check answers**: *omit* irrelevant sections ("only show sections that are relevant"); show
  **"Not provided"** for an applicable optional question left blank. That is a two-way distinction in a
  learner-facing summary: not shown vs asked-and-blank.
  <https://design-system.service.gov.uk/patterns/check-answers/>
- **SurveyJS** exposes the choice as configuration: `clearInvisibleValues` defaults to `"onComplete"`
  (invisible values are cleared when the survey completes), alternatives `"none"` (keep them),
  `"onHidden"` / `"onHiddenContainer"` (clear the moment they are hidden); per-question
  `clearIfInvisible`. A hidden question therefore reads as *blank in the results* only when clearing
  is on, which is "not asked" and "asked, blank" collapsing together.
  <https://surveyjs.io/form-library/documentation/api-reference/question.md>
  <https://github.com/surveyjs/survey-library/issues/35>
  (This matches the idea's choice: keep while in progress, delete at submission. The cited
  `research_answer_lifecycle_and_reporting.md` has the data-side comparison.)
- **MoJ Form Builder** hides disconnected pages from users but lists them for authors, a precedent for
  a *different view per audience* of the same structure.
  <http://formbuilder-product-page.apps.live.cloud-platform.service.justice.gov.uk/branching/>

I found no vendor documentation specifically on how an *educator or admin* sees a skipped question in a
submitted response. This is a gap in public sources, not an assertion that it is unsolved.

### Options for the FLS views, as UX patterns

| View | Option A: omit | Option B: show muted "Not asked" / "Skipped (did not apply)" | Notes |
|---|---|---|---|
| Learner check-your-answers (`check_your_answers.html`) | GOV.UK default; matches "only show relevant sections". | Reveals the branch to the applicant ("why does it say not asked?"). | Idea file decides: off-path rows never reach the page. A fully skipped `FormPage` card should disappear (no empty card). |
| Admin `_answers.html` | Cleaner; hides the path. | Lets a reviewer see the form had a question they were not given. | Today both missing-answer causes print the same "Not answered". After this feature, "Not answered" (asked, blank) and "not asked" are different facts; the one word becomes ambiguous unless the two are worded differently. |
| Educator/report views | Per-learner tables with different question sets are hard to compare. | A fixed column set with a distinct not-asked cell keeps columns aligned. | `freedom_ls/reports/` reads `scores["max_score"]` per attempt (idea file). A column that is empty for non-applicable learners must not read as zero. |

The persisted-path record in the idea file is what makes Option B reliable: "not asked" can be read
from what the sitting recorded rather than recomputed from current conditions (the idea's own
argument for freezing). Without it, an educator opening an old response after an author edits a
condition sees a "not asked" label that contradicts what the applicant saw.

Wording is a UX choice no source standardises. Candidates seen across the sources: GOV.UK "Not
provided" (asked, blank); none found for not-asked. Keep the two phrases visibly distinct, and keep
"Not answered" for the asked-and-blank case so existing admin copy keeps its meaning.

---

## 6. Author-facing UX

Context: FLS authors write YAML files; a mistake surfaces at `content_save` / `content_engine/validate.py`
time, not in a visual builder. Most competitor tooling is GUI. What transfers is the *feedback
contract*, not the interface.

### Visual flow and logic summaries (GUI tools)

- **MoJ Form Builder**: the "form flow view" draws branches as arrows; saving a branching point
  rearranges pages and shows new paths; rules are applied top to bottom with first match winning and
  cannot be reordered; a loop is *possible* ("Page 3 leads back to page 4") and the guidance treats it
  as the author's job to fix; unconnected pages are shown in a separate section.
  <http://formbuilder-product-page.apps.live.cloud-platform.service.justice.gov.uk/branching/>
- **Typeform**: a "Logic Map" shows routes, an eye icon previews/test-runs (third-party tutorial; may
  describe an older builder). Staff statements in community threads: logic jumps work only forward.
  Community reports of preview confusion (previewing without filling answers shows the
  first-required-field jump).
  <https://makerpad.zapier.com/posts/logic-based-lead-forms-in-typeform>,
  <https://community.typeform.com/questions/4052>
- **SurveyMonkey**: "Preview the survey to test all possible logic paths before sending"; responses
  are not recorded in preview; skip logic is only evaluated when the respondent clicks Next.
  <https://help.surveymonkey.com/en/surveymonkey/create/troubleshooting-skip-logic/>,
  <https://www.surveymonkey.com/curiosity/3-common-skip-logic-mistakes/>
- **GOV.UK Forms** features page does not describe a preview or route-error UX. Not stated.
  <https://www.forms.service.gov.uk/features>

### Validation of references (expression-based tools)

- **SurveyJS** added expression validation (Survey Creator v2.5.6-2.5.7): reports unknown variables or
  references to missing question/panel/page names, unregistered functions, syntax errors, and
  *semantic errors* (an expression that always evaluates to the same value); the result carries the
  element and property holding the bad expression. Release notes list that it "displays only one error
  at a time" as a known issue; older versions only logged console warnings.
  <https://www.componentsource.com/product/surveyjs-survey-creator/releases/2944416>,
  <https://SurveyJS.io/stay-updated/release-notes/v1.9.111>
  Relevance: the *always-constant condition* error class maps to the idea's "literal that matches no
  `QuestionOption.value`" check; the "one error at a time" known issue is a negative example for
  an importer that stops at the first problem.
- Qualtrics' check-for-errors page could not be retrieved (404); no claim made.

### Patterns for file-based authors (derived, partly from the above)

1. **Report all problems in one run, each with file, page, question and key.** Already FLS's
   voice (`Form.validate_quiz_fields` quotes `file_path`). SurveyJS's one-at-a-time limitation is the
   cautionary case.
2. **Name the failing rule in plain words, not just "invalid".** For the five rejections in the idea
   file, a message form that states what was found, where, and what would fix it. Examples of
   structure only (not a proposal of final copy): "`when.question` is `employer_paid` but no question
   in this form has that slug. Did you mean `employer_pays`?"; "`when.question` `employer_pays` is on
   page 2, the same page as the question it controls; a condition's source must be on an earlier
   page."; "`when.equals` is `yes` but `employer_pays` has options `y`, `n`".
   Listing the valid slugs/option values in the message is the single highest-value affordance in a
   file-first workflow, because the author cannot hover or autocomplete.
   - "Did you mean" for near-miss slugs: Python's `difflib.get_close_matches` is the common stdlib way;
     no cited product source for the practice in form builders, so it is a suggestion only.
3. **Duplicate slug errors name both locations.** The idea requires slug unique within a form.
4. **Cycle error prints the chain** (`a -> b -> a`), the format graph tools use. Given the earlier-page
   rule a cycle is impossible if the earlier-page check passes, so this message is mostly redundant;
   it would appear only if the rule check were reordered after the cycle check.
5. **A "dry-run a path" aid.** The sources all treat *preview of a chosen path* as the author's
   confidence tool (SurveyMonkey's "test all possible logic paths", Typeform's preview/Logic Map).
   Public docs do not say how a code-first author is meant to do this. Options visible in the shape of
   the problem, none sourced: (a) a management command that takes `slug=value` pairs and prints the
   resulting page/question list; (b) an admin preview that renders the sitting for a chosen set of
   answers; (c) a printed outline of the form with each condition inline and a "reachable? yes/no/
   depends" marker. Which of these fits is a spec decision.
6. **Condition-in-context display.** Authors editing a page file see the condition next to the
   question it gates (the `when:` block in the YAML example already does), but not the reverse: which
   questions depend on `employer_pays`. When renaming a slug, the reverse direction is what breaks. A
   "who depends on this" listing in the same error or a validate-only report is the standard
   remedy in tools that support refactoring; no source on form builders found.
7. **Silent-never-true is the dangerous class.** The idea file already calls out the typo'd value. SurveyJS
   treats "always the same value" as a first-class semantic error, which is evidence that tool authors
   found it common enough to build for.

---

## 7. FLS implications (no implementation plan)

1. **Progress copy needs a policy per runner.** The course player has a fixed `total_question_count`
   and "Page N of M" in four places; the application shell shows no "of M". The reliable options in
   the sources are: no denominator, or a denominator recomputed at render from the live path. A path
   whose total changes mid-sitting is the exact case Agriculture and GOV.UK say to avoid or reinterpret.
   The idea file's decision to recompute `answered_counts` is consistent but not the only conforming
   choice; the numerator-only alternative needs no path knowledge.
2. **"Page N of M" is a second counter the idea file does not mention.** It is `current_page_num` of
   `total_pages` (all authored pages), repeated in the visible indicator, the progress bar width, the
   sr-only `<h1>` and the `aria-live` announcement. If it stays an absolute authored page number,
   the learner reads "Page 4 of 6" on their second screen. This sits in a11y-relevant markup (the
   `aria-live` region and `<h1>`), so the wording is a deliberate change, not a rendering detail.
3. **Page identity vs label.** URL page numbers stay as identity (index into `form.pages.all()`); the
   nav label, "Page N" fallback in check-your-answers, the dots' `aria-label` and the sr-only edit text
   all need a path-derived label or a title. Untitled pages would show shifting "Page N".
4. **All-steps navigators are discouraged for conditional sections by GOV.UK itself.** The existing
   note already says to omit skipped pages; this adds that the *dots/links nav as a whole* is the
   GOV.UK-flagged pattern. It is not a reason to remove the nav (it is a product feature), but it
   explains why omission is a patch rather than a clean fit.
5. **Check-your-answers loop**: `?return=check` is a one-bit "go straight back" marker. The
   documented pattern requires a conditional redirect after an accepted POST (next newly applicable
   unanswered page, else review). The page-level buttons ("Save and return to your answers" /
   "Back to your answers") need per-page copy. The required-answer error names a stable ordinal that
   may not be visible on review and carries no link.
6. **Resume has no sourced norm.** The decisive question is not "skipped vs not" (settled in the idea)
   but "land earlier or later when the furthest page is now skipped", and keeping the resume ceiling and
   the page-jump ceiling (`page_accessibility_limit`) in agreement.
7. **"Not answered" becomes ambiguous.** After this feature the admin `_answers.html` and
   `check_your_answers.html` both print "Not answered" for a missing row. If the admin view shows
   not-asked questions at all, the two causes need different wording. For the learner review, GOV.UK's
   precedent is to omit irrelevant sections entirely and to say "Not provided" for applicable blanks.
8. **Empty cards.** A `FormPage` skipped in full renders as a card with no rows on check-your-answers
   today (the template loops over `section.rows` without an empty check). Omit the whole card.
9. **Author feedback contract**: the idea's five import rejections are each a distinct message;
   evidence from SurveyJS says authors need all errors at once, naming file + page + key, and that
   "always constant" conditions should be errors. Listing valid slugs/option values in the message
   compensates for the lack of a GUI. How an author dry-runs a path in a file-first workflow has no
   precedent found in public docs and is an open spec question.
10. **Educator/report presentation**: a not-asked cell must look unlike a zero and unlike
    asked-and-blank; the frozen path record from the idea is what lets old responses keep the label
    they were given.

---

## Sources

- [GOV.UK Design System, Check answers](https://design-system.service.gov.uk/patterns/check-answers/)
- [GOV.UK Design System, Question pages (progress indicators)](https://design-system.service.gov.uk/patterns/question-pages/)
- [GOV.UK Design System, Step by step navigation](https://design-system.service.gov.uk/patterns/step-by-step-navigation/)
- [GOV.UK Design System, Validation](https://design-system.service.gov.uk/patterns/validation/)
- [GOV.UK design notes, One thing per page](https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/)
- [GOV.UK Prototype Kit, Let the user change answers](https://prototype-kit.service.gov.uk/make-first-prototype/let-user-change-answers/)
- [GOV.UK Prototype Kit, Conditional content](https://prototype-kit.service.gov.uk/docs/conditional-content)
- [GOV.UK Forms, features](https://www.forms.service.gov.uk/features)
- [GOV.UK Forms, forthcoming features](https://forms.service.gov.uk/forthcoming-features)
- [MoJ Form Builder, Branching](http://formbuilder-product-page.apps.live.cloud-platform.service.justice.gov.uk/branching/)
- [MoJ Digital blog, save for later in MoJ Forms](https://mojdigital.blog.gov.uk/2023/10/26/balancing-security-and-usability-to-add-save-for-later-to-moj-forms/)
- [Canada.ca alpha, return to a partially filled form](https://articles.alpha.canada.ca/forms-formulaires/return-to-partially-filled-form/)
- [Agriculture Design System, Progress indicator](https://design-system.agriculture.gov.au/components/progress-indicator)
- [NSW Design System community, Progress indicators](https://community.designsystem.nsw.gov.au/t/progress-indicators/669)
- [Alberta design system, progress indicator with multiple questions](https://design.alberta.ca/examples/show-a-simple-progress-indicator-on-a-question-page-with-multiple-questions)
- [SurveyJS, Question API (clearIfInvisible)](https://surveyjs.io/form-library/documentation/api-reference/question.md)
- [SurveyJS library issue 35 (clearInvisibleValues origin)](https://github.com/surveyjs/survey-library/issues/35)
- [SurveyJS Survey Creator 2.5.7 release notes (expression validation)](https://www.componentsource.com/product/surveyjs-survey-creator/releases/2944416)
- [SurveyJS v1.9.111 release notes](https://SurveyJS.io/stay-updated/release-notes/v1.9.111)
- [SurveyMonkey, troubleshooting skip logic](https://help.surveymonkey.com/en/surveymonkey/create/troubleshooting-skip-logic/)
- [SurveyMonkey, 3 common skip logic mistakes](https://www.surveymonkey.com/curiosity/3-common-skip-logic-mistakes/)
- [Typeform community, logic jump thread](https://community.typeform.com/questions/4052)
- [Zapier Makerpad, logic-based lead forms in Typeform](https://makerpad.zapier.com/posts/logic-based-lead-forms-in-typeform)
- [Jotform answers, save and come back later](https://jotform.com/answers/1355730-is-there-a-way-to-save-and-come-back-later-to-complete)

In-repo files read: `freedom_ls/form_engine/paging.py`, `freedom_ls/form_engine/page_flow.py`,
`freedom_ls/course_applications/views.py` (lines 700-850), `.../check_your_answers.html`,
`.../form_page.html`, `freedom_ls/learner_interface/templates/learner_interface/course_form_page.html`,
`freedom_ls/form_engine/templates/admin/form_engine/_answers.html`.

Not retrieved (stated, not claimed): Qualtrics survey-checker page (404), forms-admin docs (404),
Typeform official docs on Logic Map, any vendor doc on educator-facing "skipped question" display.

---

status: ok
reason: gaps 1-5 covered with cited sources and FLS screen mapping; public sources are thin on resume-under-branching and admin not-asked display, flagged as such
