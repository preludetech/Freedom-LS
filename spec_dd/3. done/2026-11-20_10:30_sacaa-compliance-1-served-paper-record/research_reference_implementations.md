# Research: how reference implementations record and replay the paper served per attempt

Date: 2026-11-17. Scope: how Moodle, Canvas Classic Quizzes, Open edX and QTI/TAO store the per-attempt paper, and what that changes in this spec's open questions. Builds on `research_randomization_ux_integrity.md` sections 3 and 6.4 (seed per attempt, explicit realised order) and does not repeat them. The FLS file references were read at HEAD 53fb74dfe.

## 1. What each system stores

### Moodle quiz: an explicit layout plus a per-question start state

- **Attempt layout.** At attempt start, `quiz_start_new_attempt` builds `quiz_attempts.layout` as a comma-separated list of **slot numbers**, with `0` marking a page break, e.g. `1,2,0,3,0`. Sections with `shufflequestions` have their slots shuffled. Every section ends on a page break. The layout is stored once and then read for the rest of the attempt. Slots are fixed per quiz, and the layout only reorders them. Source: `mod/quiz/locallib.php` (`$attempt->layout = implode(',', $layout);`), https://raw.githubusercontent.com/moodle/moodle/MOODLE_405_STABLE/mod/quiz/locallib.php ; `quiz_sections.shufflequestions` is "Whether the question order within this section should be shuffled for each attempt", https://raw.githubusercontent.com/moodle/moodle/MOODLE_405_STABLE/mod/quiz/db/install.xml
- **Attempt to question usage.** `quiz_attempts.uniqueid` is a "Foreign key reference to the question_usage that holds the details of the question_attempts that make up this quiz attempt" (install.xml above). The usage stores one `question_attempt` per slot. Each one records `questionid`, `variant`, **`maxmark`**, `minfraction` and plain-text summaries of the question, response and right answer. Source: https://docs.moodle.org/dev/Overview_of_the_Moodle_question_engine
- **Random draw.** A random slot is resolved at start, and the **chosen** question id is written into that slot's `question_attempt`. The draw is not re-run later. `maxmark[$slot]` is copied from the quiz slot at start and passed to `add_question` (locallib.php above).
- **Option order.** Multichoice `start_attempt` writes the answer-id order into the first step's data as `_order` (`implode(',', $this->order)`, shuffled when `shuffleanswers` is set). `apply_attempt_state` reads it back on every later load. This is an explicit order, not a seed. Source: https://raw.githubusercontent.com/moodle/moodle/MOODLE_405_STABLE/question/type/multichoice/question.php
- **Deleted options.** `apply_attempt_state` handles ids in `_order` that no longer exist. The code comment reads "Sometimes people edit questions after they have been attempted which breaks things." For each missing id it builds a placeholder answer labelled "deleted choice", with `fraction = 0`. The stored order therefore keeps its length, and the gap stays visible (same file).
- **Content edits.** Since 4.0, questions are versioned. A `question_attempt` points at the version it was started with, and review still shows that version after a newer one exists (tracker test case MDL-77745, https://tracker.moodle.org/browse/MDL-77745). Moodle covers "survives later edits" with versioned content, not with references to live rows.
- **Replay.** Regrading replays the stored step history: "we need to play back the entire sequence of what the student did" (question engine overview above). Totals are stored on the attempt (`sumgrades`, "Total marks for this attempt").

### Canvas Classic Quizzes: a full snapshot per submission

- `Quiz#generate_submission` sets `submission.quiz_data` to `builder.build_submission_questions(...)`. It also stores `submission.quiz_version = version_number`. https://raw.githubusercontent.com/instructure/canvas-lms/master/app/models/quizzes/quiz.rb
- `QuizQuestionBuilder` draws questions from groups and banks (`pool.draw(... pick_count)`), shuffles answers, and stores the **full question hash** per submission: question text, answers, `position` and `points_possible`. This is a frozen copy, not references. https://raw.githubusercontent.com/instructure/canvas-lms/master/app/models/quizzes/quiz_question_builder.rb
- `quiz_version` drives "needs review" after a quiz edit: completed submissions on an older version are checked with `changed_significantly_since?` (quiz.rb above). Canvas flags edits against stored attempts. It does not silently rescore them.

### Open edX: seed only, re-derived on every render

- A capa problem keeps `seed = Integer(help="Random seed for this student", scope=Scope.user_state)`. Choice shuffle (`<choicegroup shuffle="true">`, with `fixed` choices) is recomputed from that seed against the **current** problem XML on each render. The order is not stored. The Randomization setting (`always`, `on_reset`, `never`, `per_student`) decides when the seed changes. Sources: https://docs.openedx.org/en/ulmo/educators/references/course_development/advanced_problem_editor.html ; seed field as quoted in https://git.andalsoftware.com/Andal.LND/edx-platform/commit/b0d41f6ebbe647d72333f37b2a8f0531f4fc7874
- The randomized content and item bank block stores the learner's `selected` children in `Scope.user_state`, an explicit list. On every load, `make_selection` **mutates** the list. Children deleted from the library are removed (`reason="invalid"`). Extras over `max_count` are dropped. New blocks are drawn at random to refill the count, and the list is reshuffled. Each change publishes `...content.removed` or `...content.assigned` events. https://raw.githubusercontent.com/openedx/edx-platform/master/xmodule/item_bank_block.py
- Result: a learner's set and order can change after an edit, so the record depends on live content. This is the anti-pattern for an audit record.

### QTI 2.x / 3 (the standard TAO implements)

- Selection and ordering "define a sequence of items for each instance of the test", and "This sequence is constant throughout the test". Selection runs "for each test session". Choice `shuffle` randomises the order in which choices are "initially presented", and `fixed` choices stay in place. https://www.imsglobal.org/question/qtiv2p1/imsqti_infov2p1.html
- QTI Results Reporting carries the served paper in the result itself. `itemResult.sequenceIndex` gives "the position of the item" in the test route, with the first item at 1. `responseVariable.choiceSequence` reports the shuffled choice order "as a sequence of choice identifiers". https://www.imsglobal.org/question/qtiv2p2/QTIv2p2-Results-InfoBindModelv1p0/imsqtiv2p2_result_v1p0_InfoBindv1p0.html (v3 keeps `sequenceIndex`: https://www.imsglobal.org/sites/default/files/spec/qti/v3/rr-bind/index.html)
- TAO's internal session store (qtism) was not verified in this pass. The standard's contract is what matters here: route fixed at session start, position and choice order reported by identifier.

## 2. Patterns across systems

| Concern | Moodle | Canvas Classic | Open edX | QTI |
|---|---|---|---|---|
| Order stored | explicit layout of slot ids | explicit, inside snapshot | seed only (capa); mutable list (item bank) | route per session; reported by index |
| Option order | explicit `_order` id list in step 1 data | baked into snapshot | re-derived from seed | `choiceSequence` of identifiers |
| Drawn subset | chosen question id per slot | in snapshot | `selected` list, refilled on edit | selection per session |
| Max mark | per question attempt, copied at start | `points_possible` in snapshot | per problem | outcome variables |
| Content edit | versioned questions | frozen copy plus "needs review" flag | follows live content | n/a |
| Deleted option | placeholder "deleted choice", 0 marks | copy unaffected | follows live content | n/a |
| When written | eagerly, at attempt creation | at submission generation | seed lazily on first load | session start |

All three systems with an audit story (Moodle, Canvas, QTI) store the realised order **explicitly, by identifier, once, at attempt start**. None of them re-derives an order from a seed for review. Open edX is the one that re-derives or mutates, and it is the weakest for audit.

## 3. What this changes in the spec

1. **Record shape (open question 1).** Follow Moodle and QTI: ordered lists of **uuids**. Use an ordered `pages` list, each entry with `{page, children: [uuid...]}`, plus an `options` map from question uuid to an ordered option-uuid list. Store option order as an explicit uuid list, like Moodle's `_order` and QTI's `choiceSequence`. Do not store a permutation index, which breaks when an option is added. Nobody in the survey uses the seed for replay. A seed is only useful as the input to a future shuffle, so keep it a separate field written once with the record, and never read it back for review. Add a `version` key to the JSON so specs 2 and 3 can extend it (for example drawn-from-pool markers) without guessing the shape.

2. **Store the served max mark, or the served question list, at start (Moodle's `maxmark`, Canvas's `points_possible`).** The idea says `max_score` is the total over served questions. Under the settled "skip deleted items on read" rule, `max_score` shrinks when a served question or option disappears. Moodle and Canvas both freeze the per-question mark at start instead. The answers already settle skip-on-read, so the spec does not need to reverse that. It should name the trade-off in its edge cases: a post-attempt deletion changes an old attempt's `max_score`, and with it `quiz_percentage` and `passed`. That conflicts with the idea's own line that no old attempt changes its score. Two narrow options: (a) score recompute uses the stored `scores` for completed attempts and only re-derives for in-progress ones, or (b) record a per-question max at start. A QUIZ question scores 1 per correct answer (`compute_quiz_scores`), so (b) is just "served question count". Recommend (a) as the smaller change, and let the spec state that the results page's "outdated score" check must not fire for a completed attempt solely because a served item was deleted.

3. **Deleted items: skip, but make it observable.** Moodle keeps a "deleted choice" placeholder and Canvas a frozen copy, so both keep the gap visible. FLS's settled answer is to drop it. For an audit trail the record itself must never be rewritten (Open edX's refill is the counter-example). The spec should say: the JSON keeps the uuid of a deleted item. Only the **reader** skips it, and the stored record still lists it. This keeps `sacaa-compliance-4-attempt-review` able to show "an item was served here and later deleted", Moodle-style, without changing this spec's behaviour.

4. **Eager vs lazy (open question 2).** Moodle and Canvas write at creation. Open edX writes the seed lazily. The answers settle on a lazy write on the attempt's next request, which also covers in-flight attempts. The reference systems point to one guard: the write must be idempotent and race-safe. Two concurrent first requests must not produce two different papers once spec 2 adds a shuffle. Specify a conditional update (`filter(pk=..., served_paper__isnull=True).update(...)`, then re-read) rather than read-modify-save. With authored order only, both writers produce the same paper today, so this matters from spec 2 on, but it belongs in this spec's write function.

5. **Navigation by position (open question 6).** Moodle's attempt URL `page` is an index into the attempt's layout, while FLS keeps the authored number in the URL (settled). Moodle's `currentpage` and QTI's `sequenceIndex` are **positions in the served route**. That supports the reinterpretation in the idea: store "furthest reached" as a served position, or keep it authored and translate on read. Following the references, store a position, because a position stays meaningful even if the authored number of a page later changes. Either way, the spec should define one translation function (authored number to served position) and route resume, `build_page_links` and `furthest_page_reached` through it.

6. **Name items by uuid, which already survives edits.** `content_save` writes each option's uuid back into the YAML (`content_save.py:176-201`, `778-780`), so option uuids are stable across re-saves. That makes uuid references as durable as Moodle's slot and answer ids. As read at HEAD, `content_save` has no pruning step for form pages, questions or options. The only stale-row `delete()` in the command is for due dates (`content_save.py:1258`). So "a served item deleted from the live form" happens through the admin, a shell or a future pruning change, not through a normal content edit. The spec's tests should delete rows directly to exercise skip-on-read.

7. **Frozen text stays out of scope, but say so as a known gap.** Canvas, and Moodle through versioning, both survive wording edits. FLS references live rows, so an edited question shows its new wording in an old attempt's review. The idea already puts frozen copies out of scope (`content_snapshots`, paused). The spec should note this as the remaining gap against `research_sacaa_requirements.md`'s "frozen content, not live references" line, so it is not lost.

## References

- Moodle quiz attempt creation: https://raw.githubusercontent.com/moodle/moodle/MOODLE_405_STABLE/mod/quiz/locallib.php
- Moodle quiz schema: https://raw.githubusercontent.com/moodle/moodle/MOODLE_405_STABLE/mod/quiz/db/install.xml
- Moodle multichoice `_order`: https://raw.githubusercontent.com/moodle/moodle/MOODLE_405_STABLE/question/type/multichoice/question.php
- Moodle question engine overview: https://docs.moodle.org/dev/Overview_of_the_Moodle_question_engine
- Moodle question versions in attempts: https://tracker.moodle.org/browse/MDL-77745 , https://tracker-old.moodle.org/browse/MDL-78025
- Canvas quiz: https://raw.githubusercontent.com/instructure/canvas-lms/master/app/models/quizzes/quiz.rb
- Canvas question builder: https://raw.githubusercontent.com/instructure/canvas-lms/master/app/models/quizzes/quiz_question_builder.rb
- Open edX item bank block: https://raw.githubusercontent.com/openedx/edx-platform/master/xmodule/item_bank_block.py
- Open edX problem editor and randomization: https://docs.openedx.org/en/ulmo/educators/references/course_development/advanced_problem_editor.html
- Open edX capa seed field: https://git.andalsoftware.com/Andal.LND/edx-platform/commit/b0d41f6ebbe647d72333f37b2a8f0531f4fc7874
- QTI 2.1 information model: https://www.imsglobal.org/question/qtiv2p1/imsqti_infov2p1.html
- QTI 2.2 results reporting binding: https://www.imsglobal.org/question/qtiv2p2/QTIv2p2-Results-InfoBindModelv1p0/imsqtiv2p2_result_v1p0_InfoBindv1p0.html
- QTI 3 results reporting binding: https://www.imsglobal.org/sites/default/files/spec/qti/v3/rr-bind/index.html

status: ok
