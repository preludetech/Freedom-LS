# UX patterns: position, resume and jump when the served order differs from the authored order

Question: what are the common UX patterns for learner navigation and position display ("page N of
M", resume, jump) when the served order differs from the authored order, and what do they change in
this spec?

This builds on `research_form_engine_seams.md` (sections 2, 3 and 6) and
`research_randomization_ux_integrity.md` (section 3, stability within an attempt) and does not
repeat them. Code paths are under `freedom_ls/` at HEAD 53fb74dfe.

## 1. What established assessment engines do

- **Moodle persists a per-attempt layout and numbers everything from it.** `quiz_attempts.layout`
  is a comma list of slots with `0` as a page break. `determine_layout()` splits it with
  `explode(',0', $this->attempt->layout)`, and `number_questions()` walks `$this->pagelayout` page by
  page and slot by slot, so the question numbers the learner sees are served positions. A
  description item gets an "i" label and does not advance the counter. The `page` URL parameter is a
  zero-based index into the attempt's own layout, which makes it a served index, not an authored one.
  Shuffle is per section (`quiz_sections.shufflequestions`, "whether the question order within this
  section should be shuffled for each attempt"). Navigation is `free` or `seq` (`quiz.navmethod`).
  Sources: <https://raw.githubusercontent.com/moodle/moodle/MOODLE_401_STABLE/mod/quiz/attemptlib.php>,
  <https://raw.githubusercontent.com/moodle/moodle/MOODLE_401_STABLE/mod/quiz/db/install.xml>,
  <https://docs.moodle.org/en/Building_Quiz>, <https://docs.moodle.org/en/Quiz_settings>.
- **Canvas New Quizzes** pairs "one question at a time" with an optional "Allow backtracking". With
  backtracking on, the learner gets Previous and a Question Navigator to jump. With it off, the
  navigator is hidden and only Next works. Source:
  <https://community.canvaslms.com/t5/Student-Guide/How-do-I-take-a-quiz-where-I-can-only-view-one-question-at-a/ta-p/292>.
- **TAO (QTI delivery)** separates linear navigation (answer in numbered order, no return) from
  non-linear (jump from a number line or overview panel). The panel shows each item's state: not
  viewed, viewed but not attempted, answered, bookmarked. Shuffle is configured per section, and a
  "Fixed" item keeps its place. Sources:
  <https://userguide.taotesting.com/user-documentation/latest/public/test-navigation-for-test-takers>,
  <https://userguide.taotesting.com/user-documentation/latest/public/test-section-settings>.
- **Accessible position display.** Design systems agree on four things: a visible or visually hidden
  "Step N of M" text, `aria-current="step"` on the current item, a labelled `nav` around an ordered
  list when the indicator can be clicked, and the number used as reinforcement rather than as the
  only carrier of state. Sources: <https://opensource.ebay.com/evo-web/components/progress-stepper/accessibility>,
  <https://designsystemproblems.pages.dev/accessibility-compliance/progress-indicator-accessibility>.

The common pattern is that everything the learner reads (page position, total, question numbers, the
navigator's order, the "furthest reached" frontier and the resume point) lives in served space.
Engines differ only on the URL. Moodle puts a served index in it, while FLS has already settled on
the authored number. Nothing in the sources requires one or the other, so the FLS choice holds, as
long as no learner-visible text or comparison ever uses the authored number.

## 2. Where FLS still compares or shows authored numbers

The seams research found the `>`/`<` comparisons in `SittingPath`. A closer read finds more sites
that the spec must name, because each one breaks on its own under an injected order.

| Site | Today | Needed under a served order |
|---|---|---|
| `SittingPath.numbered_pages`, `_page_positions` (conditions.py:52-77) | enumerate `all_pages` in authored order | iterate the served page list; `page_position` becomes the served place |
| `next_page_number`, `previous_page_number`, `first_page_number_at_or_after`, `last_page_number`, `landing_page_number` (conditions.py:115-130) | authored `>`, `<`, `>=` | the next or previous entry in served order; return the authored number for the URL |
| `get_current_page_number` (models.py:367) | first authored page with an unanswered question | first in served order |
| `_furthest_answered_page` (paging.py:32) | `max` of authored numbers | the served-last page with an answer |
| `_resume_page_number` (paging.py:44) | `max` of three authored numbers, clamped to `len(all_pages)` | `max` of three served indexes, clamped, then mapped to an authored number |
| `record_page_reached` (models.py:356) | `page_number <= furthest_page_reached` | compare served indexes |
| `build_page_links` (paging.py:86) | authored order, `number <= limit` | served order, served index `<= limit`; the label stays `page_position`, the url stays authored |
| `first_page_number_with_unanswered_required(after=)` (paging.py:149) | `number > after` | served index `> after` |
| results page, `course_form_complete.html:105` | `Question {{ item.question.question_number }}`; `FormQuestion.question_number()` (models.py:236) walks the **authored** form | the question's served number from the sitting's path; list in served order |
| `get_incorrect_quiz_answers` (models.py:655) | walks `form.pages.all()` in authored order | walk the served path, so the list order matches what the learner saw |
| option inputs (`inputs/multiple_choice.html:12`, `checkboxes.html:2`, `dropdown.html:11`) | `question.options.all` in authored order | the record's option order (see 4) |

`question_positions()` and the error messages built on it (`_question_numbers`, paging.py:165)
already follow the path, so they come right for free once the path is built from the record.

The results-page finding is new. Even with no shuffle, `question_number()` reads the live form, so a
question added later renumbers an old attempt's results. Under an injected order, "Question 3" on
the results page names a different question from the "Question 3" the learner answered. The usual
pattern (Moodle `number_questions()`) is that the review numbering is the attempt's numbering.

## 3. "Furthest page reached" and resume: one served index, not a position

Two quantities exist and the spec should name them separately, because the code already mixes them:

- **served index**: the 1-based place of a page in the attempt's full served page list. Pages off
  the path are counted. This is what comparisons and the stored frontier use.
- **position**: the 1-based place among the on-path pages, which is what "page N of M" shows
  (`page_position`).

Recommendation: `furthest_page_reached` stores a served index. For any attempt in authored order
(every record-less attempt, every non-quiz form, and every quiz until shuffle lands), the served
index of a page equals its authored number. So the column keeps its meaning for every existing row
and needs no data migration, and the course-applications flow (course_applications/views.py:791),
which shares this code, sees no change. Storing the on-path position instead would break
conditional application forms, where positions shift as answers turn pages on and off. Storing the
authored number and translating on every read also works, but every comparison then needs two
lookups.

Deleted items. The answers say "skip on read". If the served index is counted over the record's own
page list, including entries whose page has since been deleted, a deletion does not shift the
indexes of later pages and the stored frontier stays valid. Display positions are counted over
surviving on-path pages only, so "page N of M" shrinks the way `max_score` does. Keep the existing
clamp in `_resume_page_number`.

## 4. Option order

The record carries option order, so the spec has to say who reads it. If the option templates keep
reading `question.options.all`, the record can claim an order the learner never saw. Once shuffle
ships, that turns the audit record false without any test failing. Recommendation: in this spec the
three input templates and the results page's answer lists read option order from the path, for
example `SittingPath.options_of(question)`. The idea's test "a refresh or resume shows the same
paper" should cover option order too. This is invisible until shuffle ships, because the injected
order is authored order everywhere except in tests.

## 5. Patterns to adopt, and to leave for later specs

Adopt in this spec (no visible change while order is authored):

- Every learner-facing number is served: page position, total, question number, dot labels, the
  results page and required-answer messages.
- The jump navigator lists pages in served order. It stays free navigation up to the frontier, as
  it is today. FLS has no sequential mode, and none is needed for SACAA.
- A stable paper across refresh, back, resume and a new device. The record already gives this. The
  dots and "Page N of M" must not reorder after a page is deleted mid-attempt, apart from the
  deleted page disappearing.
- Accessibility: the dots already carry `aria-label="Page {{ page.number }}"`
  (`course_form_page.html:36`), where `number` is the position, and the sr-only `h1` reads "Page N
  of M" (line 234). Both stay. Adding `aria-current="step"` (or `"page"`) on the current dot follows
  the common pattern, but it is a polish item outside this spec.

Leave for later (record in the spec as out of scope):

- **Authored numbers in URLs can identify pages.** Under a page shuffle, two learners can line up
  `.../page/3/` across their papers, which partly undoes the anti-collusion purpose of shuffling.
  Moodle avoids this with served indexes in the URL. FLS has settled on authored URLs, so
  `sacaa-compliance-2-shuffle` should note this as an accepted risk. Questions within a page and
  options carry no URL identity, so only the page shuffle is affected.
- **Direct URL jump past the frontier.** `is_accessible` only greys out a dot; no view refuses a page
  number beyond `page_accessibility_limit` (it has no caller outside paging.py). The behaviour is
  the same as today and not this spec's concern, but the spec should not claim that page-jump is
  "restricted".
- A review screen with per-question status (answered, flagged) like TAO's overview, flag-for-review
  and a no-backtracking mode are all common in exam engines. None is requested.

## 6. Spec changes this implies

1. Add the results page to the surfaces that follow the served paper. Question numbers come from the
   sitting's path, not `FormQuestion.question_number()`, and the incorrect-answers list follows
   served order. Add a test: with an injected order, the results page shows the served numbers.
2. Settle the open "positions semantics" question: `furthest_page_reached` stores a served index
   over the record's full page list, and it equals the authored number in authored order, so no
   data migration is needed. Name "served index" and "position" as separate terms, and check
   `fls-dev:domain-glossary` for existing nouns first.
3. List every comparison site from the table in section 2. The "next, previous, resume and
   page-jump" tests should include `first_page_number_with_unanswered_required` (the final-submit
   redirect to the first page with an outstanding required question) and `get_current_page_number`.
4. Say that the option inputs read option order from the record in this spec, and extend the
   round-trip and refresh test to option order.
5. In Out of scope, add: the URL identity under page shuffle (hand it to
   `sacaa-compliance-2-shuffle`), server-side enforcement of the page-jump frontier, and the
   `aria-current` polish.

status: ok
