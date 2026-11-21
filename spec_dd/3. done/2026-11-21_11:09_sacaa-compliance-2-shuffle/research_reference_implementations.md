# Research: Reference implementations of shuffle, lock and keep-together (code level)

Topic: how Moodle, Open edX, QTI and open-source Python/Django quiz apps implement seeding, lock insertion, group atoms, and storage and rendering of the realised order. This goes one level below `research_randomization_ux_integrity.md`. Where I could not read the source and am relying on memory or a secondary summary, the text says so ("unverified").

Method note: sources were read through a fetch-and-summarise tool, so code quotes are short fragments and paraphrase surrounds them. Moodle's repo moved code under `public/` (path used below). Open edX capa source was read from the `open-release/redwood.master` branch (the `master` path 404s).

---

## 1. Moodle

### 1.1 Option shuffle: `qtype_multichoice` (flag at start, order stored as a step variable)

Source: `public/question/type/multichoice/question.php`.

Algorithm, `start_attempt()` (runs once, when the question attempt is created):

```php
$this->order = array_keys($this->answers);
if ($this->shuffleanswers) {
    shuffle($this->order);
}
$step->set_qt_var('_order', implode(',', $this->order));
```

- Uses PHP's global `shuffle()`. There is no seed. The result is persisted, not re-derivable.
- Data shape: the realised option order is a comma-separated string of answer ids, e.g. `"12,15,11,14"`. It is stored as a question-type variable (`_order`) on the attempt's first "step" (Moodle's append-only event log for a question attempt).
- Restore, `apply_attempt_state()`: `$this->order = explode(',', $step->get_qt_var('_order'));`. `get_order()` calls `init_order()`, which falls back to `$qa->get_step(0)->get_qt_var('_order')`.
- `shuffleanswers` is read only in `start_attempt()`. It is a no-op after the attempt exists, so editing the flag mid-attempt cannot change what a learner sees.
- Rendering: the renderer iterates `$question->get_order($qa)` and looks up each answer by id, so DOM order equals stored order.
- Versioning detail (from the docblock of `update_attempt_state_data_for_new_version()`): when a question is edited and a new version is swapped in, Moodle must "shuffle the new list of ids in the same way that the old one was". This is the cost of storing only ids that live in the live question tables. It supports the idea's rule that the served-paper record, not re-derivation, is authoritative.
- There is NO lock/fixed option in `qtype_multichoice`. The shuffle is all-or-nothing per question, and Moodle docs advise rewording "All of the above". (Other Moodle types, for example ordering/matching, have their own handling; not read.) So Moodle gives no model for the lock; QTI and Open edX do.

### 1.2 Question order: quiz attempt `layout` (flat string, `0` = page break)

Source: `public/mod/quiz/locallib.php` `quiz_start_new_attempt()`; read side `public/mod/quiz/classes/quiz_attempt.php` `determine_layout()`.

Data shape: `quiz_attempts.layout` is one comma-separated string of **slot numbers** (a slot is a stable position in the quiz definition, not a question id), with `0` terminating each page. Example: `3,1,0,2,4,0` is slots 3 and 1 on page 1, then slots 2 and 4 on page 2. Read side: `explode(',0', $layout)` into pages, then `explode(',', ...)` into slots.

Build algorithm (once, at attempt start):

1. Compute each section's slot range `[firstslot, lastslot]`. Sections are contiguous slot ranges, so a shuffle never moves a question across a section boundary.
2. For a section with `shufflequestions`: collect its slots, `shuffle($questionsinthissection)`, then **re-paginate by count**: start a new page (append `0`) whenever the page holds `questionsperpage` questions. Page breaks authored inside a shuffled section are discarded.
3. For an unshuffled section: keep slot order, insert `0` only where the stored page number of consecutive slots changes.
4. After every section, append `0`, so a section always ends a page.
5. `$attempt->layout = implode(',', $layout)`.

Lessons for FLS:

- Moodle's shuffle unit is the **section**, and the shuffle scope is the section. Shuffling never crosses a section. FLS pages play a similar role: the `shuffle_questions` knob shuffles within a page, and `shuffle_pages` shuffles page order.
- Moodle shuffles slots (positions), so number display, "requires previous question" blocking and the review all need to know about it. Concretely `quiz_attempt` special-cases shuffled sections in three places: `number_questions()` ignores custom display numbers (sequential numbers by served position), `is_blocked_by_previous_question()` skips the dependency rule, and `determine_layout()` cannot assume `firstslot` is first. FLS equivalent: question numbers follow served order (the idea already says so), and anything that assumes authored position (progress, "next page", first-question checks) must read the served order.
- Moodle has no group atom. The Moodle forum thread on randomising groups of questions (cited in the earlier research) confirms the gap. The workaround is a separate section (shuffle off in it).
- Moodle's "random question" slots (`mod_quiz\local\structure\slot_random`) are a pool draw, not a shuffle; they resolve to a concrete question at attempt start. Relevant to `sacaa-compliance-3-question-pools`, not here.

### 1.3 Seeding

Moodle does not seed. It shuffles once and stores the result. Reproducibility comes from the stored order only.

---

## 2. Open edX (capa `choicegroup`)

Sources: `xmodule/capa/responsetypes.py` (`MultipleChoiceResponse.do_shuffle`, `shuffle_choices`, `get_rng`), `xmodule/capa/capa_problem.py` (seed handling), course-author docs (URL below).

### 2.1 Authoring syntax

```xml
<multiplechoiceresponse>
  <choicegroup type="MultipleChoice" shuffle="true">
    <choice correct="false">A</choice>
    <choice correct="true">B</choice>
    <choice correct="false" fixed="true">All of the above</choice>
  </choicegroup>
</multiplechoiceresponse>
```

`shuffle` is on the group; `fixed` is a per-choice flag beside `correct`. This is the same shape the idea suggests (`locked` beside `correct`). `shuffle` together with `answer-pool` raises the author error "Do not use shuffle and answer-pool at the same time" (precedent for a validator rejecting an incompatible combination).

### 2.2 Lock insertion algorithm (`shuffle_choices`): head / middle / tail, NOT absolute positions

From the source as summarised (code read from redwood branch):

- Leading `fixed` choices form a `head` that stays first.
- Fixed choices that come after the first non-fixed choice go to a `tail` that stays last.
- `rng.shuffle(middle)` shuffles only the remaining choices.
- A fixed "island" in the middle of the list is grouped with the tail (moved to the end), so a fixed choice authored in the middle does NOT keep its absolute position.

Contrast with the idea: the FLS idea says locked options keep their **absolute authored positions** and unlocked options fill the remaining positions. QTI and Canvas behave like the idea (position retained); Open edX only really supports "fixed at the start or end". Absolute-position insertion is the more general rule, and for "All of the above" at the end both agree. A concrete absolute-position algorithm is in section 5.

### 2.3 Seed

- `get_rng()` creates one `random.Random(self.context['seed'])` and caches it on the problem (`problem._shared_rng`), so every response in a problem draws from one generator (comment: keeps multi-question problems from looking predictable).
- Seed priority in `capa_problem.py`: `self.seed = state.get('seed', seed)`: first the seed stored in the learner's per-problem state, else the constructor argument; it asserts "Seed must be provided". `get_state()` returns `'seed': self.seed`, so the seed is persisted per learner per problem.
- Where the constructor seed comes from (user id versus a per-attempt value, and rerandomize-on-reset behaviour) was not verified in this pass. Treat as unverified.
- Data shape: Open edX stores the seed, not the order. The order is re-derived from seed + problem XML on each render. That is exactly the fragility the earlier research flagged (the shuffle must be deterministic across Python versions, and the XML must not change). Open edX also has an earlier-era masking feature (obfuscating choice names, `unmask_order`) that is disabled in current code ("appears to not be fully implemented"), so it is not a model.

---

## 3. QTI (2.2 and 3)

Sources: QTI 2.2 and 3 implementation guides and information models (URLs below). The fetch tool returned the choice-level text but could not reach the section-level attribute definitions, so the section rules below are unverified from this pass and should be re-checked against sections 4.2 (`qti-assessment-section`), 5.x (`ordering`) of the 3.0.1 information model before the spec cites them.

Verified (QTI 3 impl guide):

```xml
<qti-choice-interaction response-identifier="RESPONSE" max-choices="1" shuffle="true">
  <qti-simple-choice identifier="A">Alpha</qti-simple-choice>
  <qti-simple-choice identifier="B" fixed="true">None of the above</qti-simple-choice>
  <qti-simple-choice identifier="C">Gamma</qti-simple-choice>
</qti-choice-interaction>
```

- `shuffle` on the interaction (default false), `fixed` on each choice (default false). The delivery engine randomises the order, **except** choices with `fixed="true"`, which "keep their position". Shuffling is a discretionary feature of the delivery engine.
- Per the guide the fixed choice stays at its authored index (position 2 above) while A and C may swap, which matches the idea's absolute-position rule.

Unverified (my recollection of the information model; the earlier research partly disagrees on `keepTogether`):

- Section ordering: `qti-ordering` child of a section with `shuffle="true"`. Applies to the **immediate children** of that section only (items and sub-sections). Children (item refs or sub-sections) with `fixed="true"` stay in position; the rest shuffle among the other positions.
- A sub-section is one child (one atom) in the parent shuffle; its own ordering decides its internal order. This is the group atom model.
- `keep-together` (`keepTogether` in 2.x) on a sub-section, default true: when true the sub-section's children are not mixed with the parent's other children during shuffle (this is the semantics I recall, and it is what makes the sub-section an atom). When false, its children may be mixed into the parent's shuffle. The earlier research file describes keepTogether as being about paging chunks; I believe that is incorrect, but this needs checking against the model text.
- `visible`: a non-visible section has no heading, so silent grouping is possible. FLS's `group:` key is effectively an invisible, keep-together sub-section.
- Seed and storage: QTI leaves this to the delivery engine. QTI results reporting (`itemResult`/`sessionIdentifier`, `candidateResponse`) is how the served order is recorded in results; the order itself is delivery-engine-specific. QTI 3 does have an `outcome`/`shuffle`-order variable for choice interactions: a response variable `...` (unverified) records the displayed order for audit.

Take-away: QTI's model is the precedent for (a) absolute-position `fixed`, (b) a nested section as the atom, (c) shuffle applying only to immediate children.

---

## 4. Open-source Python/Django quiz apps

I found no Django quiz app that stores a per-attempt seed or implements positional locks. What exists:

### 4.1 `django_quiz` (tomwalker lineage; PyPI `django-quiz-app`)

Sources: `quiz/models.py`, `multichoice/models.py` in `tomwalker/django_quiz`.

- `Sitting` model holds the attempt. `question_order` (CharField 1024, validated comma-separated integer list) is "a list of integer pks of all the questions in the quiz, in order", and `question_list` is the unanswered remainder (same format).
- `SittingManager.new_sitting` builds it once: `quiz.question_set.all().select_subclasses().order_by('?')` when `quiz.random_order`, optional truncation `[:max_questions]`, then `",".join(map(str, ids)) + ","` into both fields. `remove_first_question` pops the head of `question_list` as the learner answers.
- Verdict: the shape (stored ordered id list on the attempt, written at creation) matches the Moodle layout and the idea's served-paper record. Weaknesses: a 1024-char CharField cap, no seed, no groups, flat only.
- Option order is a counter-example: `MCQuestion.order_answers(queryset)` does `queryset.order_by('?')` for `answer_order == 'random'` (other values: `content`, `none`). That is re-run on every render, so the options reshuffle on every page load and are never stored. This is exactly the failure mode the idea rules out (reload shows a different order, no audit trail). FLS must not copy it. The same goes for any DB-level random order in templates.

### 4.2 Others

`django-easy-quiz` and the `kallewesterling`/`sawadkk`/`dbf` forks of `django_quiz`: forks of the same design, not read in detail. The Laravel pattern "shuffle with a seed gives the same order for the same seed" (second parameter of seeded shuffle) is the general seeded idiom.

---

## 5. Concrete algorithms and data shapes to take into the spec

All of these are my synthesis from the above, not copied code.

### 5.1 Seeded shuffle (determinism)

- Moodle stores the result only, Open edX stores the seed only. The idea stores the result in the served-paper record, so the seed need only drive the one-time shuffle at attempt start. The seed can still be stored for debugging.
- Use a dedicated `random.Random(seed)` instance, never `random.seed()` or the module-level functions (thread safety, no global state; Open edX does the same with a shared `random.Random`). `random.Random(str)` seeding with a str is deterministic across Python 3 versions (version 2 seeding via sha512), but only `shuffle()` called with the same sequence of operations reproduces; hence store the output rather than rely on re-derivation.
- Use one `Random` per attempt and shuffle in a fixed traversal order (pages, then per page atoms, then per question options). A single shared generator is what Open edX does. Alternatively derive a per-scope child `Random(f"{seed}:{page_id}:{question_id}")` so adding or removing a question does not change the other scopes' orders. The second is better for reproducing when content changes, but is irrelevant if the result is stored.

### 5.2 Lock insertion (absolute positions)

```python
def shuffle_with_locks(items, is_locked, rng):
    n = len(items)
    free = [it for it in items if not is_locked(it)]
    rng.shuffle(free)
    free_iter = iter(free)
    return [items[i] if is_locked(items[i]) else next(free_iter) for i in range(n)]
```

Locked items keep their absolute index, free items fill the remaining slots in shuffled order. QTI `fixed` has the same shape. Open edX's head/middle/tail is a subset (equivalent when locked items are only at the ends). Edge cases to settle in the spec: all items locked (no-op), one free item (no-op), and whether a locked option in the middle is allowed (idea says yes).

Reproducibility note: the number and order of `rng` calls depends on `len(free)`, which is stable for a given content version.

### 5.3 Group atoms on a page

Model (per answers.md: `group: <name>` string on each member, contiguous run, no nesting):

1. Walk the page children in authored order. A maximal run of children with the same non-empty `group` key becomes one atom (a list of children, order preserved). Every other child is a one-element atom. (QTI: a sub-section; Moodle: a section.)
2. If `shuffle_questions` is on: shuffle the list of atoms with the seeded `Random`. If off: leave atoms in authored order (groups still resolve as atoms, which the pools spec needs).
3. Flatten atoms back to a child list. Never shuffle inside an atom.
4. Validator: same key appearing in two non-adjacent runs, or on two pages, is an error (idea). A page-scoped key means `group` need not be globally unique, but the same key on two pages is rejected per the idea. Nesting is not expressible with a flat string key, so the answers.md rule needs no syntax beyond that.

Both QTI and Canvas make the atom a first-class container (section or stimulus). The flat string key is cheaper and is the string-key variant of the same idea; its cost is that adjacency has to be validated (the validator rule in the idea).

### 5.4 Page-level shuffle

Shuffle the list of pages with the seeded `Random` (QTI: shuffle immediate children of the root section). No page lock (answers.md). Moodle never shuffles across sections, so there is no direct precedent for a full page shuffle; QTI's `ordering` on a root section is the closest.

### 5.5 Stored realised order: shape

Two shapes exist in the references:

| System | Shape | Granularity |
| --- | --- | --- |
| Moodle `quiz_attempts.layout` | one string of slot numbers, `0` = page break | questions and pages |
| Moodle `_order` step var | CSV of answer ids per question attempt | options |
| django_quiz `Sitting.question_order` | CSV of question pks | questions |
| Open edX | seed only | everything |

Proposed JSON (one blob, one write at attempt start), consistent with the earlier research's `realized_order` but using stable ids and carrying the page structure:

```json
{
  "seed": "<uuid>",
  "pages": [
    {
      "page": "<page id>",
      "items": [
        {"kind": "content", "id": "<content id>", "group": "diagram-1"},
        {"kind": "question", "id": "<question id>", "group": "diagram-1",
         "options": ["<opt id>", "<opt id>", "<opt id>"]},
        {"kind": "question", "id": "<question id>", "group": null,
         "options": ["<opt id>", "<opt id>"]}
      ]
    }
  ]
}
```

Notes: flat `items` per page (groups recorded as a tag, items already flattened in group order) keeps rendering a simple loop and keeps the record readable for the audit spec. The question number is the 1-based index of question items in page order across pages (Moodle `number_questions()` does sequential numbering by served position when the section is shuffled).

### 5.6 Rendering

- Moodle: the renderer iterates the stored order and fetches each answer by id. No ORM `order_by` on the render path. FLS: the three input templates should receive an already-ordered option list built from the stored id list (one `in_bulk()` fetch then `[by_id[i] for i in ids]`), never `question.options.all()`.
- Pitfalls the references show: (1) re-running `order_by('?')` per request (django_quiz); (2) code that assumes first slot / authored position is first (Moodle needed three special cases); (3) numbering shown by authored position, which mismatches what the learner sees; (4) editing content under a live attempt (Moodle's new-version reshuffle problem).
- DOM order equals visual order, which holds automatically when the template iterates the stored list and no CSS reorder is used (idea, WCAG 1.3.2 and 2.4.3).

### 5.7 Answers to the idea's "open until the spec" points that the references inform

- Group model: QTI/Canvas use a container; Moodle uses sections; none use a string key. A string key works because the atom is derived at shuffle time and stored flat, as long as the validator enforces contiguity.
- Groups with the page shuffle off: QTI allows it (sections can be unshuffled children), so there is precedent.
- Seed: store it (cheap, helps debugging and tests) but rely on the stored order. Moodle shows no seed is needed.
- Where the function lives: Moodle puts the build in `quiz_start_new_attempt()` (attempt creation), and the question type does option shuffle in `start_attempt()`. Mirror it as one pure function, `(form structure, seed) -> realised order`, called once from attempt creation, and unit-tested without a database.
- Validator: Open edX's "do not use shuffle and answer-pool at the same time" is a precedent for an explicit, plain error message at authoring time.

---

## Reference URLs

Moodle:
- https://raw.githubusercontent.com/moodle/moodle/main/public/question/type/multichoice/question.php
- https://raw.githubusercontent.com/moodle/moodle/main/public/question/type/questionbase.php
- https://raw.githubusercontent.com/moodle/moodle/main/public/mod/quiz/locallib.php (`quiz_start_new_attempt`)
- https://raw.githubusercontent.com/moodle/moodle/main/public/mod/quiz/classes/quiz_attempt.php (`determine_layout`, `number_questions`, `is_blocked_by_previous_question`)
- https://raw.githubusercontent.com/moodle/moodle/main/public/mod/quiz/classes/local/structure/slot_random.php

Open edX:
- https://raw.githubusercontent.com/openedx/edx-platform/open-release/redwood.master/xmodule/capa/responsetypes.py
- https://raw.githubusercontent.com/openedx/edx-platform/open-release/palm.master/xmodule/capa/capa_problem.py
- https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-koa.master/exercises_tools/multiple_choice.html
- 2014 shuffle/answer-pool commit (mirror, not read in full): https://git.andalsoftware.com/Andal.LND/edx-platform/src/commit/ab7d3b526b01fc16e170a013b9cbd6a27a0136b7

QTI:
- https://www.imsglobal.org/spec/qti/v3p0/impl
- https://www.imsglobal.org/sites/default/files/spec/qti/v3/info/index.html (sections `qti-assessment-section`, `qti-ordering`, item ref `fixed`: not read in full)
- https://www.imsglobal.org/question/qtiv2p2/QTIv2p2-ASI-InformationModelv1p0/imsqtiv2p2_asi_v1p0_InfoModelv1p0.html
- https://www.imsglobal.org/question/qtiv2p2/imsqti_v2p2_impl.html

Django / Python:
- https://raw.githubusercontent.com/tomwalker/django_quiz/master/quiz/models.py
- https://raw.githubusercontent.com/tomwalker/django_quiz/master/multichoice/models.py
- https://pypi.org/project/django-quiz-app/0.4.0/

Gaps to close before the spec cites them: exact QTI 3 `keep-together` / `fixed`-on-section semantics (info model sections 4.2 and `ordering`); how Open edX derives the initial per-learner seed and whether it changes on reset.

---

status: ok
reason: Moodle, Open edX and django_quiz read at code level; QTI section-level semantics and the Open edX initial seed source are flagged unverified
