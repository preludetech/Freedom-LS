# Research: best practices for seeded quiz shuffling (gaps beyond the randomisation UX research)

Scope: the gaps left by `research_randomization_ux_integrity.md`. That file covers QTI, Moodle, Canvas
and Open edX comparisons, the lock and group concepts, seed-per-attempt, stored order and DOM order.
This file does not repeat them. Items marked [own reasoning] are engineering judgement, not a cited
source.

## 1. Seeded shuffle algorithm in Python

### 1.1 `random.Random(seed)` vs `secrets` / `SystemRandom`

- `random.Random(seed).shuffle()` is a Fisher-Yates style in-place shuffle. It is unbiased up to the
  Mersenne Twister's limits. It is reproducible for a fixed seed on one Python version.
- `random.SystemRandom` and `secrets` read `os.urandom`. The docs say `SystemRandom` "does not rely
  on software state, and sequences are not reproducible", `seed()` is ignored and `getstate()` raises
  `NotImplementedError`. They are therefore the wrong tool for replaying a shuffle from a seed.
- The `random` docs warn the module "should not be used for security purposes". The right split is:
  - generate the per-attempt seed with `secrets` (for example `secrets.randbits(64)` or
    `secrets.token_hex(16)`), so a learner cannot predict a later attempt's order or another
    learner's;
  - consume the seed with a local `random.Random(seed)` instance to do the shuffle.
  Predicting the order is a copying aid, not a credential, so Mersenne Twister is acceptable once the
  seed is unguessable [own reasoning]. Never use the module-level `random.shuffle` (shared global
  state, breaks determinism under threads and other callers).
- Always use a private `Random` instance. Never call `random.seed()` globally.
- Reproducibility caveat from the docs: only `random()` output for a given seed is guaranteed stable
  across Python versions. `shuffle`, `sample` and `choice` are explicitly "subject to change". A
  string seed uses `version=2`, which hashes all bits of the string. Python 3.11 removed the
  `random=` argument of `shuffle`.
- Consequence for FLS: the stored served-paper record, not the seed, must be the authority (the idea
  already says so). Store the seed anyway as an audit aid, but never promise that re-running the
  shuffle reproduces a past attempt after a Python upgrade. A Django upgrade or Python upgrade
  must not change any stored attempt, because nothing re-derives it.
- Version-independent alternative if a replay guarantee is ever wanted [own reasoning]: do not use
  `shuffle`. Give each atom a sort key `sha256(f"{seed}:{scope}:{atom_key}")` and sort by it. This
  depends only on SHA-256, which is stable forever, and is a uniform random permutation (256-bit keys
  make ties negligible). It also makes each scope independent of iteration order (see 1.3). This is
  the only approach that survives interpreter changes without a stored record, and it is simple to
  test. Either is defensible given the record is stored; choose one and pin it with a golden test
  (section 6).

### 1.2 Uniformity with locked positions

Locked options keep absolute authored positions. The unlocked options fill the remaining slots.

Correct algorithm:
1. `locked = {i: opt}` for each locked option at index `i`; `free = [opts not locked]`.
2. Shuffle `free` with the seeded RNG.
3. Build the result by walking indexes `0..n-1`: take `locked[i]` if present, else `next(free_iter)`.

This gives a uniform random permutation of the unlocked options over the unlocked slots. That is
exactly the "shuffle among the remaining positions" semantic in the idea. Pitfalls:
- Do not shuffle everything and then swap the locked ones back: it displaces whatever landed in the
  locked slot and biases which options end up adjacent to it.
- Do not insert locked options into the shuffled list by position one by one in arbitrary order. Insert in
  ascending index order or use the slot-walk above; descending or random order gives wrong positions
  when two options are locked.
- Edge cases to test: no locked options (plain shuffle), all locked (identity), one free option
  (identity), lock on index 0 and on the last index, two locks adjacent, a lock in the middle.
- A QTI `fixed="true"` choice behaves the same way. QTI 2.2 implementation text: fixed choices keep
  their position and the rest are shuffled. Open edX does the same. (URLs in section 8.)
- A one-element or all-locked option set produces identity, which is fine and must not raise.
- Document that "unlocked options shuffle" does not guarantee the order differs from authored; with
  3 free options there is a 1 in 6 chance of the same order. Do not retry to force a difference
  (retrying biases the distribution and the idea does not ask for it).

### 1.3 Independent scopes: derive a sub-seed per scope

Do not draw all three knobs from one RNG stream in loop order. If one stream is consumed page by page,
adding a question to page 1 changes the shuffle of page 2 and of every option set after it. Derive a
child RNG per scope from the attempt seed [own reasoning]:

- pages: `Random(f"{seed}:pages")`
- children of page P: `Random(f"{seed}:page:{page_key}")`
- options of question Q: `Random(f"{seed}:options:{question_key}")`

Benefits: toggling one knob does not change the other knobs' results; an edit to one page does not
reshuffle unrelated pages; each scope can be tested alone. Use stable content keys (the question's
UUID or authored slug), not list indexes or database ids that can change. This also fits the
seed-only-at-start rule: the same code path serves attempt start and any later test replay.

## 2. Shuffling atoms while preserving group order

Established pattern (QTI nested non-shuffled `assessmentSection`, Canvas stimulus, Gradescope
subquestion groups; covered in the earlier research): treat each group as a single atom, shuffle
atoms, then flatten.

Implementation recipe [own reasoning]:
1. Build atoms in authored order by one pass over the page's children: a run of consecutive children
   with the same `group` key becomes one atom (a list), anything else is a one-element atom.
2. If the page-level knob is on, shuffle the list of atoms. Do not shuffle the members.
3. Flatten atoms into the served child sequence. Members of an atom keep authored order.
4. If the knob is off, flatten without shuffling. Atoms still exist so
   `sacaa-compliance-3-question-pools` can draw them as units; expose atom building as its own
   function (`build_atoms(children) -> list[list[Child]]`), separate from `shuffle(atoms, rng)`.
   That separation gives pools the same unit and lets the shuffle be unit-tested without the ORM.
5. Atoms are keyed for the sub-seed by the group key (or the lone child's key). A page can have two
   groups with the same string key only if the validator forbids it (section 5).

Uniformity note: atoms of different sizes are shuffled uniformly as atoms, so a 4-item group is as
likely to be first as a lone question. This is the established behaviour (QTI shuffles sections as
units). Authors should know a group's position, not its members' positions, is what is randomised.

Contiguity rule: the answer file says contiguous run with the same key is one atom. Decide and
document what the loader does with a non-contiguous repeat of a key. The validator must reject it
(idea says so); do not silently merge, because merging would move content the author never grouped.

## 3. Numbering shown to learners under shuffle

Established practice:
- Moodle: question numbers follow the order served to the student, and are renumbered per attempt. The
  review shows the same served numbers. Moodle's quiz navigation block lists questions in served order.
- Canvas: questions in a shuffled quiz show in the order served; the numbers in the question header
  follow position. Educators looking at a student's submission see that student's order.
- Moodle and Canvas both document the same author guidance: do not write "see question 3" or "the
  previous question" in shuffled quizzes.

Recommended for FLS [own reasoning, consistent with the idea's "numbers follow the order served"]:
- Number questions only, counting 1..N across the whole served paper in served order. Content blocks
  take no number. Number from the served list, never from the database `order` or the `forloop` of the
  unshuffled query. Compute the number once when the served-paper record is built and store it, or
  derive it by one counting pass over the record, so the results and review pages show identical
  numbers.
- Pages: if page numbers or "Page 2 of 4" labels are shown, they follow served page order too.
  Page titles are authored text and move with the page; authors must not write "Part 1" in a page title
  of a quiz with shuffled pages unless they accept that "Part 2" can be served first. State this in the
  `fls-content` docs next to the cross-reference warning.
- Internal references: validator cannot reliably detect "question 3" in free text, so use a soft warning
  at most (regex for `question \d+`, `Q\d+`, "above", "below", "previous", "all of the above", "both A
  and B", "option [A-D]") rather than an error. Because every flagged pattern has false positives, make
  it a warning and never block save.
- Option labels: if options are shown with letters (A, B, C), assign letters by served position, not
  by authored position; authored letters inside the option text ("A. Foo") must be rejected or warned
  when shuffle_options is on, since they would display out of order.
- The answer key and educator preview keep authored numbering (idea). Label them "authored order" so
  staff do not compare a key number with a learner's served number. Per-attempt review (spec 4) should
  show the served number, optionally the authored number beside it.
- Do not number content blocks and keep-together groups on a progress indicator: a group of 3 questions
  counts as 3 questions, not 1.

## 4. Accessibility of reordered forms

Beyond the DOM-order rule already in the idea:
- WCAG 2.2 Understanding 1.3.2 Meaningful Sequence: the programmatic (DOM) order must carry the
  meaning; technique C27 is "Making the DOM order match the visual order". CSS repositioning is only
  tolerable when meaning does not depend on order, and failure F1 applies when it does. A shuffled
  quiz where DOM and visual differ fails this, so render the served list and use no CSS `order`,
  `flex-direction: *-reverse` or grid placement. See 2.4.3 Focus Order (same reasoning for tab order).
- Radio, checkbox and dropdown groups: keep `<fieldset>` + `<legend>` (the question text) so screen
  reader users get the question as the group label. Reordering must not change `name`, `id` or
  `for`/`id` pairs; derive ids from the option's primary key, not from its position index. Position-based
  ids (`opt_1`, `opt_2`) rebind labels incorrectly after a shuffle and are a common bug.
- Stable across re-renders: an HTMX swap or a 422 validation re-render must reuse the stored order. A
  re-render that shuffles again changes what a screen reader announces and moves focus targets,
  which is both a usability and a WCAG 3.2.x (consistent behaviour) risk.
- Question numbers in headings or `aria-label`s: use the served number, so "Question 3" read by a screen
  reader matches the sighted label.
- Positional text in options ("the option above", "all of the above") is also an accessibility defect
  because screen reader users hear options in sequence and cannot see layout; the lock fixes
  position but the authoring guide should still say to prefer "All of the listed statements are
  correct".
- Keep-together groups: render the stimulus before its questions in the DOM; if the stimulus is a
  figure, give it text alternative as for any image. A group could be wrapped in a `<section>` or
  `role="group"` with an `aria-labelledby` pointing to the stimulus heading if it has one (optional;
  do not add a wrapper that changes existing markup for unshuffled forms).
- Cognitive accessibility: shuffled order is a known burden for some learners with cognitive
  disabilities. Extended-time and accommodation policies are an operational matter; do not build a
  per-learner "do not shuffle" override (out of scope) but say in the docs that opt-in per quiz exists
  partly for this reason, and that formative quizzes should usually leave shuffling off. [own reasoning]

## 5. Authoring validation rules

Collected from the idea, the answers and the established systems (QTI, Open edX, Canvas); each rule
should have a stable error code or wording so tests can assert it [own reasoning unless stated].

Strategy and knobs
1. Any of `shuffle_pages`, `shuffle_questions`, `shuffle_options`, any option `locked`, any `group`
   on a form whose scoring strategy is not QUIZ: error naming the field and the strategy.
2. Knob values must be real booleans, not the strings `"false"`/`"no"` (YAML/front matter pitfalls:
   `"false"` is truthy). Reject non-bool.
3. A knob in a page header: error (answer 3: form-level only). Better an explicit error than silent
   ignore; unknown keys must not be swallowed.

Locks
4. `locked` on an option of a form with `shuffle_options` off: error (idea).
5. `locked` on a question type with no option order (free text, number, etc.): error.
6. Lock combinations that make shuffling meaningless: a question with fewer than two unlocked options
   (zero or one free option) when shuffle_options is on. Make this a warning, not an error: a
   "True/False" question with nothing to move is legitimate in a form where options shuffle for other
   questions, and the shuffle is simply the identity.
7. Positional-text lint (warning): options whose text matches `all of the above`, `none of the above`,
   `both`, `\b[A-D]\b only`, `options? \d` and are not locked; suggest locking or rewriting.
   Open edX and Canvas guidance lists these same phrases as the standard hazard.
8. Locked option position is the authored index; reordering options in the source changes where it
   locks. Document that the lock is positional by authored order.

Groups
9. Same-key members must be a contiguous run on one page; a repeat of the key after a different child
   is an error, as is the same key on two pages (idea).
10. No nested groups (answer 2): a member that declares two keys or a group syntax inside a group is
    an error. Because groups are a flat string key, nesting can only occur if the syntax allows
    path-like keys; reject keys with the separator characters you choose.
11. Group key hygiene: non-empty after stripping, bounded length, no leading/trailing whitespace; compare
    case-sensitively and say so (or normalise and warn on near-duplicates such as `Fig1`/`fig1`).
12. A group of one member is allowed but is a lint warning (probably forgot to group). A group with no
    question (only content blocks) is a warning. A group whose first member is a question and not a
    content block is allowed; the "stimulus first" rule in the idea is an authoring convention, since
    the order is preserved as authored and the validator does not enforce a kind sequence.
13. Group key must be unique per page by contiguity rule (above), but may repeat across forms.
14. Group on a page whose within-page shuffle is off: allowed (answer 2), no error, no warning.
15. With `shuffle_pages` on and one page: allowed no-op, warning optional.

Both
16. Errors must carry the file and the item, so a course author can find them. Collect all errors
    in one pass rather than failing on the first, as the existing validator presumably does.
17. `content_save` (and the schema) must treat missing keys as the off default so existing content
    needs no edits; a re-save of an old form must not set any knob.

## 6. Testing randomised behaviour deterministically

Practices (general testing guidance; also follows from the design):
- Make the shuffle a pure function of `(atoms_or_options, seed_or_rng)`. No clock, no global
  state, no DB access. Inject the RNG (a `random.Random` instance) so tests pass their own.
- Seeded tests: pass fixed seeds. Assert properties, not exact orders, where the exact order may
  change on Python upgrade:
  - the output is a permutation of the input (same multiset, no loss or duplication);
  - locked options are at their authored indexes;
  - group members are consecutive and in authored order, for every seed in a range (loop a few hundred
    seeds, cheap);
  - same seed twice gives the identical output; two different seeds differ for a large enough input;
  - toggling one knob off leaves the other scopes' results unchanged (sub-seed isolation, 1.3);
  - appending a question to page 1 does not change page 2's order (sub-seed isolation).
- One or two golden tests with literal expected output for a fixed seed. If the implementation uses
  `Random.shuffle`, the golden may break on a Python upgrade, and that is a feature (it tells you
  stored-record logic matters) but costs maintenance; if hash-key sort is used, goldens never break.
  Decide with the 1.1 choice and note it in the spec.
- Statistical uniformity test, kept cheap and deterministic: for 3 free options, run 6000 seeds
  (`range(6000)`, so the run is the same each time) and assert each of the 6 permutations occurs within
  a wide tolerance (for example 800 to 1200). A fixed seed set makes it non-flaky. For locked positions,
  assert the same over the free permutations only. Do not test with unseeded randomness and a tolerance:
  that is a flaky test.
- Stubbed RNG for algorithm branches: a fake `Random` whose `shuffle` reverses the list (or whose sort
  keys are controlled) lets a test hit "everything moved" without seed hunting.
- End-to-end through the app: start an attempt twice with controlled seeds (patch the seed generator,
  not `random`), assert that the stored record is written once, that reloading the page, the back
  button and resume return the same order, that a retake with a new seed differs, and that the
  rendered HTML option order equals the stored order (parse the DOM; check the option ids appear in
  served order and there is no CSS `order` style). Mock the seed source as the one injection point
  so tests never patch `random.shuffle`.
- Existing quizzes: a regression test that a form with all knobs off yields the authored order with no
  RNG call (assert the RNG is never consumed, for example with a RNG that raises).
- Do not freeze real `secrets` output; test the seed generator only for type, length and that two
  calls differ.
- Property-based testing (Hypothesis) fits well: generate arbitrary option lists with random lock
  masks and arbitrary page children with random contiguous groups, assert the invariants above.
  Add only if Hypothesis is already a project dependency; otherwise a seeded loop does the same job
  and avoids a new dependency. (The project rule is not to build what is not requested; this is a
  test-tooling choice for the spec to make.)

## 7. Other points worth putting in the spec

- Seed type: store as a string or big integer in the record; do not store only in a Python `hash()`,
  which is salted per process. Do not use `hash()` of a string anywhere in the shuffle path.
- Do not derive the seed from the user id or the attempt id alone: attempt ids are guessable, so
  learners could compute each other's order. Generate with `secrets` (1.1).
- Content edited after the attempt starts: because the record stores keys, scoring and review use
  the stored list and must tolerate a deleted question by the usual served-paper rules (spec 1); this
  spec need not handle it but must put only stable identifiers in what it hands to the record.
- Pool draw (spec 3) must run before shuffle on the same atoms; keep `build_atoms`, draw and shuffle as
  three separate functions so spec 3 can slot between atom building and shuffling.
- Docs for course authors (`fls-content`): say it is not proctoring, give the "no cross references, no
  positional options, group the stimulus" checklist, and show the shuffled demo.

## 8. References

- Python `random` module (reproducibility notes, `seed`, `shuffle`, `SystemRandom`, security warning):
  https://docs.python.org/3/library/random.html
- Python `secrets` module: https://docs.python.org/3/library/secrets.html
- Fisher-Yates shuffle (algorithm and the biased "naive swap" pitfall):
  https://en.wikipedia.org/wiki/Fisher%E2%80%93Yates_shuffle
- WCAG 2.2 Understanding SC 1.3.2 Meaningful Sequence (C27, F1):
  https://www.w3.org/WAI/WCAG22/Understanding/meaningful-sequence.html
- WCAG 2.2 Understanding SC 2.4.3 Focus Order: https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html
- QTI 2.2 Information Model (shuffle, `fixed`, section ordering):
  https://www.imsglobal.org/question/qtiv2p2/QTIv2p2-ASI-InformationModelv1p0/imsqtiv2p2_asi_v1p0_InfoModelv1p0.html
- Open edX multiple choice problem (shuffle and fixed options):
  https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-olive.master/exercises_tools/multiple_choice.html
- Canvas shuffling guidance (University of Saskatchewan):
  https://teaching.usask.ca/articles/2025-03-04-shuffling-questions-and-answer-options-in-canvas-quizzes.php
- Moodle: Promoting Academic Integrity in Quizzes: https://teaching-resources.delta.ncsu.edu/quiz-academic-integrity/
- Hypothesis (optional property-based testing): https://hypothesis.readthedocs.io/

Only the Python `random` and WCAG 1.3.2 pages were fetched during this pass. The other URLs are carried
over from the earlier research file or are standard documentation pages cited from knowledge; items
tagged [own reasoning] are not sourced.

---

status: ok
reason: gaps covered (algorithm, locks, atoms, numbering, accessibility, validation, testing); only two sources re-fetched this pass
