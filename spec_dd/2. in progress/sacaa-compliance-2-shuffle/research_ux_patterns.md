# Research: UX patterns for shuffle, option locks and keep-together groups

Scope: authoring syntax in text-based formats, authoring warnings and validation wording, learner-side
behaviour. It builds on `research_randomization_ux_integrity.md` (QTI `fixed`, Open edX `fixed`,
Canvas lock, QTI nested sections) and does not repeat it. Settled answers in `answers.md`: group is a
`group:` string key, form-level knobs only, no page lock, groups allowed on unshuffled pages, no
nested groups.

Confidence note: several sources below are search summaries or vendor/university guides, not primary
specs. Items marked [unverified] could not be confirmed from a fetched page.

## 1. Authoring syntax in text-based quiz formats

| Format | Question-order shuffle | Option shuffle | Pin an option | Group/stimulus |
|---|---|---|---|---|
| Moodle GIFT | none in the file | none in the file; "Shuffle the choices" is set per question after import | none | none |
| Moodle Aiken | none | none (import options do not affect Aiken) | none | none |
| QTI 2.x/3 XML | `<ordering shuffle="true">` on a section | `shuffle="true"` on the interaction | `fixed="true"` on a choice | nested `assessmentSection` |
| Open edX OLX | none in the problem; section level elsewhere | `shuffle="true"` on `<choicegroup>` | `fixed="true"` on `<choice>`, only effective when shuffle is on | none |
| Obsidian better-quizbox (markdown) | n/a | automatic option shuffling | no pin found | none |
| Articulate Rise/Storyline | per quiz | per question | users ask for anchoring; not built in | none |

Findings.

1. **The text-only quiz formats (GIFT, Aiken) carry no shuffle syntax at all.** Shuffle is a UI
   setting applied after import. The documented workaround for "All of the above" is to untick shuffle
   on those questions by hand after import. This is the failure mode a text-first FLS should avoid:
   the shuffle intent lives next to the content, in the file, so it round-trips and is reviewable in
   git. Sources: Moodle GIFT page (no shuffle text found), Moodle Aiken docs, GIFT tips blog.
2. **Where a format has it, the pattern is two-level: a container flag plus a per-option marker.**
   QTI and Open edX both put `shuffle` on the option container and `fixed` on the individual option.
   Open edX states `fixed` "only takes effect while shuffle is true" on the choicegroup. A lock with
   no shuffle is inert there, whereas FLS has chosen to make it a validation error (see section 3),
   which is stricter and better: silent inertness hides authoring mistakes.
3. **Naming.** Established terms: `shuffle` (QTI, Open edX, Moodle, Canvas) and `fixed` (QTI, Open
   edX). Canvas calls it "lock" in the UI. FLS's idea uses `locked`; `fixed` has the wider
   precedent in the two text/XML formats, `locked` matches the project's idea.md and the Canvas UI
   word. Either is defensible; recommend keeping `locked` (already in idea.md and the "position
   lock" vocabulary) and noting `fixed` in the authoring docs as the QTI/Open edX equivalent so
   authors migrating from those find it.
4. **Grouping has no flat-text precedent.** QTI uses nesting (XML elements). No GIFT/Aiken/OLX
   problem format offers a flat per-item group key. The FLS `group: <name>` flat key is therefore
   novel; the closest analogue is a shared label on items (like Canvas New Quizzes' Stimulus parent).
   Consequences for the design: the contiguity rule and the "no nesting" rule are FLS-defined, so
   the docs must show a worked example of each and the validator must explain them (section 3).
5. **Per-form placement.** In QTI and Open edX the flag sits on the container being shuffled (section,
   choicegroup), which maps to FLS form front matter for pages/questions. For options, the QTI/OLX
   precedent is a flag on the question (container), but FLS has settled on a form-level
   `shuffle_options` only. Canvas Classic is the same all-or-nothing scope and is the most
   complained-about: authors with one "None of the above" question must turn shuffle off for the whole
   quiz or work around it. The per-option lock is what resolves that, so the lock is a required
   companion to a form-level option knob, not an optional extra.
6. **Booleans are the convention.** `shuffle: true` / `fixed: true` / `shuffle_options: true` are
   plain booleans everywhere found; none use enum strings. Matches the YAML front matter style.

Suggested illustrative syntax (not decided; for the spec to settle), consistent with idea.md and
answers.md:

```yaml
# form.md front matter
shuffle_pages: true
shuffle_questions: true
shuffle_options: true
```
```yaml
# page file, question option and group, key names indicative only
- type: content
  group: wing-diagram
- type: question
  group: wing-diagram
  options:
    - text: Option A
      correct: true
    - text: All of the above
      locked: true
```

## 2. Warning authors about positional wording

What other systems do:

- **Documentation only.** Canvas Classic, Moodle and Iowa State guides: "do not shuffle answers
  unless you are certain no question has answers based on response order". No tooling detects
  positional wording; the author must know.
- **Rewrite advice.** Macquarie's Moodle guidance: change "All of the above" to "All of the other
  options", or use "All of these answers", which is order-independent. The university guides list the
  hazard phrases: "All of the above", "Answers A and B", "None of the above".
- **Anchor instead.** Open edX docs: you can shuffle some answers and keep "All of the above" at the
  end via `fixed`. QTI's own implementation guide shows shuffle combined with fixing one choice.
- **Detection is absent everywhere found.** No system found lints option text for "above", "both A
  and B", "option 1", letters. [unverified: no negative proof, only that none turned up.]

Implications for FLS (author-facing, in the `fls-content` plugin docs and optionally the validator):

1. State the hazard list as a short checklist in the docs: "all of the above", "none of the above",
   "both A and B", "options 1 and 3", "C only", and "the diagram above" / "your previous answer"
   (cross-question, covered by the group).
2. Prefer rewrite over lock when possible, then lock when not: worded as a decision order (rewrite
   to order-independent wording; else lock; else turn option shuffle off).
3. An optional **non-blocking** check is feasible: the validator could emit a warning (not an error)
   when an option on a `shuffle_options` form has text matching a small case-insensitive phrase list
   ("all of the above", "none of the above", "both a and b", "above", "previous question") and is
   not `locked`. This would be novel (no precedent found) and carries a false-positive risk, so it is
   an open choice for the spec; idea.md "Don't build functionality not requested" argues for docs
   only unless the spec adds it. If added, it must be a warning, since a wrong error would block
   legitimate content (e.g. "above" in a physics question).
4. Cross-question references ("refer to question 3") cannot be detected reliably and are out of
   validator reach; documentation only.

## 3. Validation error wording

No fetched source documents validator message text for shuffle (QTI is schema-validated; Moodle and
Open edX silently ignore or apply). So this section is design guidance drawn from the principle
that a good error names the thing, says what is wrong, and says how to fix it, using the author's own
keywords.

Recommended message shape: `<where>: <what is wrong>. <how to fix>.` Include file path, page and
question/option identity in the same manner existing validator messages do (follow the existing
validator's location format; not re-surveyed here). Draft wording for each case in idea.md:

| Case | Draft wording |
|---|---|
| Knob on non-QUIZ form | `Form "X": shuffle_options is only allowed on QUIZ forms (this form scores as CATEGORY_VALUE_SUM). Remove shuffle_options or change the scoring strategy.` One error per offending knob, naming the key. |
| Lock with option shuffle off | `Question "Q", option "All of the above": locked has no effect because shuffle_options is not enabled on this form. Set shuffle_options: true in the form front matter or remove locked.` |
| Group non-contiguous | `Group "wing-diagram" on page "P" is not a contiguous run: items 2, 3 and 5 share the group but item 4 does not. Move item 4 out or put it in the group.` |
| Group spans pages | `Group "wing-diagram" appears on pages "P1" and "P2". A group must stay on one page.` |
| Nested group | `Item "I" is in group "a" and group "b". Groups cannot be nested; use one group key per item.` Note: a flat string key makes true nesting inexpressible; the real error is more likely "an item lists two groups" if the key accepts a list, or "reused key after a gap" (which is the non-contiguous case). The spec should decide whether `group` accepts only a scalar, which makes this case impossible rather than an error. |
| Lock on every option | Optional: `Question "Q": all options are locked so shuffling would do nothing.` Likely a warning, not required. |

Principles: name the YAML key the author typed; say the rule once; give the fix; one error per
problem, not a cascade; report all errors in a pass rather than the first only (matches the batch
style authors expect from a content validator, [unverified for the existing FLS validator]).
Distinguish error (cannot import) from warning (suspicious but valid).

## 4. Learner-side patterns

### 4.1 Question numbering under shuffle

- **Numbering follows the served order, computed by the platform, never authored.** Canvas
  community answers: the numbers are generated automatically; authors should not hand-number
  questions. Canvas's own idea board has a request "Numbering questions in a quiz", and an
  instructor report that the order in the editor differed from what students saw, showing the
  edit view and student view are separate. Moodle numbers by position in the attempt (navigation
  panel shows positions in the served order) [unverified: general knowledge, not fetched].
- Consequence: idea.md's "question numbers follow the order served" matches industry practice. The
  authoring docs should tell authors not to hard-code numbers or "Question 3" in text.
- Stimulus groups: no source covered numbering within a group; the simple rule is that group
  members number consecutively, in authored order, and the group's position in the page decides
  where the run starts.
- Review pages (educator and learner post-attempt): Moodle and Canvas show the learner's own
  attempt in served order. The roadmap's educator-facing view is
  `sacaa-compliance-4-attempt-review`, out of scope here.

### 4.2 Telling learners the order is shuffled

- No source found shows Moodle, Canvas or QTI engines telling learners that order is shuffled; the
  usual stance is silence. Students notice only when comparing with others. The only guidance found
  is instructor-side: with question shuffling, "all students get the same questions, but in a
  different order", which instructors may state in the exam brief.
- Recommended for FLS: no automatic banner by default (consistent with the idea: shuffle is
  invisible), but the authoring docs advise authors to add one sentence to the form body
  ("question and option order differs between attempts") when relevant, since the form body is
  where instructions go (answers.md, page-lock question). A banner would also be a content change
  that touches the rendering seam owned by the served-paper spec.
- Where wording does reference position (e.g. "refer to the diagram above"), the group guarantees it
  holds; without a group it breaks (the research file Section 5.3).

### 4.3 Stability on back, reload and resume

- Moodle: "the order of choices within each question will be randomly shuffled each time a student
  attempts this quiz", i.e. per attempt, not per page load, and an attempt resumes in the same order.
  Canvas: shuffle is per attempt, not per view (community threads). QTI delivery engines persist the
  session's item order.
- Known failure mode: the Canvas New Quizzes thread where a lock "doesn't work" and the Canvas
  editor view reshuffling on each open show what the author sees when shuffle is implemented at
  render time. For FLS the served-paper record fixes this: render only from the record.
- HTMX consequence: partial refreshes (save answer, next/previous page) must read the stored order;
  none may call the shuffle function. Option template tests should assert the same order across two
  GETs and after an answer POST.
- Retake: new attempt, new order. Because of the stored record, the previous attempt keeps its
  order on review.
- A browser-level wrinkle worth a test: browser back/forward cache and the HTMX history snapshot
  restore previously rendered DOM; this is stable by construction because the DOM was rendered from
  the record, but a cached page from before a resume must not be re-sorted client-side. No client
  reordering code should exist.

### 4.4 Adjacent learner-side points

- Option letters: if the UI shows labels (A, B, C) they must be assigned from the served position,
  not stored with the option. Any wording "choose A or B" in a question is a positional hazard like
  "All of the above" and belongs on the hazard list. The three option templates currently
  use radio, checkbox and dropdown inputs without letters per idea.md, so lettering is not required
  but must not be added from authored order.
- Keyboard and screen-reader order: DOM order equals visual order; see the research file Section 5.4.
- Dropdown inputs: shuffling an option list in a dropdown has the same stability need; Canvas
  community has a feature request for fixed ordering of dropdown answers in fill-in-the-blank
  questions, which suggests learners/authors notice unexpected reordering in dropdowns specifically.

## 5. Take-aways for the spec

1. Keep the three knobs, `locked` option marker and `group` key as plain YAML keys next to the content
   (text formats elsewhere force the author to fix shuffle by hand after import; FLS avoids that).
2. Mention `fixed` (QTI, Open edX) in the docs as the equivalent of `locked`.
3. Lock without option shuffle is an error (stricter than Open edX); the same for group-related and
   non-QUIZ errors, in the `<where>: <what>. <fix>.` shape, naming the key.
4. Decide whether `group` is a scalar only, which makes "nested" structurally impossible, and what
   "nested groups" validation then means (idea.md lists nesting as a validation error).
5. Positional-wording lint is optional, novel, and should be a warning, not an error; the default
   position is documentation-only with a hazard checklist and a "rewrite, then lock, then turn off"
   decision order.
6. Learner side: no hard-coded numbers; numbers and any labels from served position; no shuffle
   banner by default; stability by rendering only from the served-paper record; test the same order
   across reloads, HTMX partials and resume.

## Reference URLs

- Moodle GIFT format: https://docs.moodle.org/en/GIFT_format
- Moodle Aiken format: https://docs.moodle.org/39/en/Aiken
- Moodle multiple choice question type: https://docs.moodle.org/en/Multiple_Choice_question_type
- Moodle shuffle within questions (legacy help): https://svnlliurexnet.gva.es/leia/mods-backports/trunk/moodle/lang/en_utf8/help/quiz/shufflewithin.html
- Moodle shuffle the choices (legacy help): https://svnlliurexnet.gva.es/leia/mods-backports/trunk/moodle/lang/en_utf8/help/quiz/shuffleanswers.html
- Waikato, shuffle quiz questions: https://www.waikato.ac.nz/students/eresources/moodle/quizzes/shuffle-quiz-questions
- Macquarie, change option ordering per attempt: https://help.ilearn.mq.edu.au/content/14/207/en/i-want-the-quiz-to-change-the-ordering-of-options-for-each-attempt.html
- GIFT formatting tips (shuffle unticked per question): https://medium.com/upeielo/some-tips-for-gift-formatting-930715dfad22
- QTI v3 implementation guide (shuffle, fixed, shuffle plus fixed example): https://www.imsglobal.org/spec/qti/v3p0/impl
- Open edX single select OLX reference (shuffle, fixed): https://docs.openedx.org/en/ulmo/educators/references/course_development/exercise_tools/single_select_xml.html
- Open edX edit single select, advanced editor: https://docs.openedx.org/en/ulmo/educators/how-tos/course_development/exercise_tools/edit_single_select_advanced.html
- Open edX partial credit multiple choice (shuffle example with "All of the above" last): https://docs.openedx.org/en/latest/educators/how-tos/course_development/exercise_tools/award_partial_credit_multiple_choice.html
- Canvas, shuffling questions and answer options (USask): https://teaching.usask.ca/articles/2025-03-04-shuffling-questions-and-answer-options-in-canvas-quizzes.php
- Canvas New Quizzes lock (UF guide): https://elearning.ufl.edu/instructor-help/new-quizzes/overview/
- Canvas thread, lock answer option report: https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-New-Quizzes-Multiple-Choice-lock-answer-option-doesn-t/td-p/240524
- Canvas idea, shuffle answers at question level: https://community.canvaslms.com/t5/Canvas-Ideas/Shuffle-answers-at-the-question-level/idi-p/329667
- Canvas idea, numbering questions: https://community.canvaslms.com/ideas/7015-numbering-questions-in-a-quiz
- Canvas idea, dropdown answer ordering: https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Shuffling-or-Fixed-Ordering-of-Dropdown-Answer/idi-p/631889
- Articulate, anchoring shuffled answers: https://community.articulate.com/discussions/articulate-quizmaker/multiple-choice-questions-anchoring-shuffled-answers
- Obsidian better-quizbox: https://community.obsidian.md/plugins/better-quizbox

---

status: ok
reason: covers authoring syntax, authoring warnings, validation wording and learner-side patterns; several vendor-guide claims marked unverified where only search summaries were available; no markdown/Quarto/H5P shuffle-pin syntax was found
