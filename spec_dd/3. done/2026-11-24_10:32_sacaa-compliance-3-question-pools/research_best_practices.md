# Research: best practices for per-attempt question draws (seeding, fairness, pool size, validation, audit)

Adds to `research_question_bank_patterns.md` (Moodle, Canvas, Articulate, QTI are not repeated). Evidence quality is flagged per section: "sourced" means a cited page says it; "inference" means my reasoning from sourced facts or general practice, to be treated as a recommendation, not a finding.

## 1. Seeded, reproducible draws

**Sourced**
- Python's `random` docs say most algorithms and seeding functions may change across Python versions. Only two things are guaranteed: a backward-compatible seeder will be kept if a new one is added, and `random()` gives the same sequence for the same seed. `shuffle`, `sample` and `choice` are not in the guarantee. See [random - Python docs](https://docs.python.org/3/library/random.html).
- NumPy's `Generator` makes no stream-stability promise across versions. Identical output needs the same BitGenerator, seed, call sequence, build and environment. The default BitGenerator is expected to change (PCG64DXSM). See [NumPy compatibility policy](https://numpy.org/devdocs/reference/random/compatibility.html) and [Upgrading PCG64](https://numpy.org/devdocs/reference/random/upgrading-pcg64.html).
- NumPy advises large seeds (128 bits or more) and passing a generator object, not a global seed ([Scientific Python: NumPy RNG](https://blog.scientific-python.org/numpy/numpy-rng/)).

**Inference (recommendations)**
1. A seed alone is not a durable audit record. A library upgrade can change what the same seed draws. So the persisted served paper (the resolved ordered list of drawn items, from `sacaa-compliance-1-served-paper-record`) is the authoritative record. The seed is a convenience for generating and for debugging, not for reconstruction. This agrees with the existing research (section 2.4, 5.6) and strengthens it: store the resolved list, and store the seed too.
2. Write the seed value onto the attempt and also record the algorithm identifier (a string such as `"python-random-v1"`). If the draw function changes later, old attempts stay interpretable.
3. Use a local `random.Random(seed)` instance, never the module-global RNG. Global state is shared across threads and requests, and any other call consumes it.
4. Generate the seed with `secrets` (CSPRNG), not from clock, attempt id or user id. A guessable seed lets a learner predict the paper if it is ever exposed (for example in a URL, an API response or a debug page). Never send the seed to the client.
5. Make the draw a pure function: `draw(items_in_authored_order, n, rng) -> ordered list`. Sort or fix the input order before sampling (authored order, not DB return order), otherwise the same seed gives different results on different queries.
6. Draw page by page from a single RNG in a fixed page order, or derive a per-page sub-seed (for example `Random(f"{seed}:{page_id}")`). Per-page sub-seeds mean adding or removing a draw on one page does not change the draw on another page. Hashing a string into `Random()` is supported for str seeds; the docs state that for str, bytes and bytearray the seed is converted via the version-2 method, which is stable.
7. Persist inside the same transaction that creates the attempt and use a uniqueness constraint (one served paper per attempt). Two concurrent start requests (double click, two tabs) must not produce two different draws. Use get-or-create semantics, and read the paper on every later request.
8. Sample without replacement (`sample`, not repeated `choice`), uniform. That is the QTI default `withReplacement=false` and Moodle's no-duplicates rule.

## 2. Fairness and pool-size guidance

**Sourced**
- ACT research shows that for a fixed test length, the average item exposure rate depends only on the ratio of pool size to test length ([ACT RR99-05](https://act.org/content/dam/act/unsecured/documents/ACT_RR99-05.pdf)). For a uniform random draw of N from M, each item is exposed with probability N/M per attempt.
- Exposure-control literature says a small pool weakens security unless selection compensates, that every item should be used (economy) but none overused (security), and that larger pools improve security ([review of exposure control](https://corpora.tika.apache.org/base/docs/govdocs1/477/477173.html); [JTLA review](https://ejournals.bc.edu/ojs/index.php/jtla/article/viewFile/1647/1482); [pool 100 vs 200 comparison](https://tdl-ir.tdl.org/signposting/describedby/f70c9e6a-01a9-4479-b9bd-70745b9d4543)). Caveat: most of this is computerised adaptive testing, so only the pool-to-length ratio logic transfers. Adaptive methods (Fade-Away, Sympson-Hetter) do not apply to a uniform draw.
- Moodle practice: if a draw asks for more questions than the category holds, the quiz errors at attempt time. Duplicate copies of the same question in a bank are not detected and can both be drawn. Small banks mean repeat questions across attempts ([Moodle random question type](https://docs.moodle.org/en/Random_question_type); [Moodle forum: repeats](https://moodle.org/mod/forum/discuss.php?d=236679)). Both are things a build-time validator can guard against: draw count against pool size (FLS already plans this), and duplicate question text on a page.
- I found no published rule of thumb for an exact pool-to-draw ratio. The sources above support the principle, not a number.

**Inference: a pool-to-draw ratio rule of thumb and the arithmetic**
- Expected overlap between two independent attempts drawing N from M is N²/M questions, so the fraction of the paper repeated on a retake is about N/M. At M = 2N about half repeats; at M = 3N about a third; at M = N every attempt is the same set (reorder only).
- Common practitioner guidance (not cited, treat as inference) is a pool of 2-3 times the draw for low-stakes retake variety, higher where exposure matters. Because the pool is per page and each page is one syllabus subject, this ratio should be judged per page. A page with N = 10 and M = 12 is valid under the spec but gives almost no retake variety.
- For a keep-together group page the unit is the group, so M and N are counted in groups. A 4-group page drawing 2 has only 6 possible papers. The number of distinct papers is C(M, N) for uniform draws before ordering. Suggest the validator may warn, not fail, when M < 2N. Warning suits the settled "pools homogeneous" authoring-guidance stance, and keeps "draw all" legal.
- Ex-ante fairness holds for a uniform draw (each learner has equal chance at each item); ex-post fairness depends on difficulty homogeneity, which the existing research covers and the idea already makes guidance only.
- Equal denominator: Canvas's `pick_count x question_points` shows the rule the idea adopts. Keep points per question uniform on drawing pages (or require equal total marks per item). If questions can carry different marks, `max_score` varies by draw. The idea's "same size per item" rule handles group size; the spec should also state what happens if question marks ever differ (today FLS counts one point per question, so this is a note, not a work item).
- Fairness across retakes (inference): a "draw afresh" retake with uniform sampling can re-serve a question the learner already got wrong. This is normal and expected in every surveyed system. Excluding previously seen questions needs history and shrinks the effective pool, so it is a later feature; the spec need only say retakes are independent.

## 3. Never exposing undrawn questions

**Inference (general secure-delivery practice; no specific source found)**
- Enforce by filtering at the data-access layer, not only in templates. Every learner-facing query (page flow, results, incorrect-answers list, any HTMX partial, any JSON or answer-submit endpoint) goes through one function that returns the served paper's items. Templates then cannot leak by iterating `page.questions`.
- Reject answer submission for a question that is not on the attempt's served paper (HTTP 404 or 422). Otherwise a learner who guesses a question id can probe the pool, and `QuestionAnswer` rows for undrawn questions would corrupt scoring.
- Review "one-hop" leaks: validation error messages, the results page "outdated score" check, progress counts ("question 3 of 12" where 12 is pool size), page-level question counts in course progress, search indexes, and cached rendered pages. Anything that shows pool size or counts to a learner leaks the ratio.
- Authoring-side counterpart: Moodle and the EASA question-bank guidance treat the bank as confidential. [EASA ECQB](https://www.easa.europa.eu/domains/aircrew-and-medical/european-central-question-bank-ecqb) states that all involved must keep the question bank confidential. In FLS the bank is the content files, so the educator preview showing pool size and N (settled in `answers.md`) is educator-only and should stay behind the educator permission.
- Demo content that ships in the repo is public, so the demo pool quiz exposes its own bank by design; document that production pool content lives in private content repositories.

## 4. Validation rules (build-time, from established practice)

Settled in the idea and confirmed by the surveyed systems: N at least 1 and at most M; QUIZ-only; no `when`; one item size per page; loose content inside groups. Additions worth considering:
- N must be an integer, not a bool and not a float. Reject `draw: true`, `draw: 2.5`, `draw: "3"` unless the schema coerces deliberately (YAML makes `true` a valid int in some parsers).
- Reject a page with `draw` and zero items. The N <= M rule covers it, but give a clear message.
- Ensure keep-together groups on a drawing page have identical question counts, and report which group differs (Canvas rejects stimulus items in banks outright; QTI leaves it to the author).
- Check that every drawn question is answerable on its own (a group is self-contained: its stimulus is inside the group). This follows from the loose-content rule.
- Reject or warn on duplicate question text on one drawing page (Moodle's undetected-duplicate problem, above).
- Warn when M < 2N on a page where N < M (see section 2). Do not block.
- Warn when the questions on a drawing page differ in marks or type in ways that make difficulty uneven. Optional, low value.
- Authoring guidance rather than validation: draw only on pages whose items are interchangeable.
- Cross-feature checks: draw plus `when` is rejected (settled). Draw with an answer-reveal or review feature that reads the whole page would show undrawn items; the validator cannot see that, so cover it in tests (see section 3).

## 5. Auditability for regulated aviation training

**Sourced**
- SACAA runs a Central Question Bank and draws per candidate sitting (already in the existing research). EASA's ECQB page requires confidentiality of the bank; the competent authority must sample-check ATO question banks and the examination process ([EASA Part-147 FAQ](https://www.easa.europa.eu/the-agency/faqs/part-147), [EASA ECQB](https://www.easa.europa.eu/domains/aircrew-and-medical/european-central-question-bank-ecqb)). EASA Part-66 requires candidates to be separated so they cannot read each other's papers (66.B.200(h), via [UK CAA GM 66.B.200](https://regulatorylibrary.caa.co.uk/1321-2014/Content/AMC%20GM/GM%2066%20B%20200%20Examination%20by.htm)).
- I did not find AMC text requiring random per-candidate papers. Treat the SACAA requirement as covered by `research_sacaa_requirements.md`, not by this research.

**Inference (what an auditor would expect from the record)**
- Each attempt needs a record that answers "exactly which questions did this learner see, in what order, and what did they answer", independent of later content edits. The served paper gives the list of items; answers are already keyed per question. Question text edits after the attempt are the `content_snapshots` problem and are explicitly out of scope, but the spec should state that the record holds references, so a later edit changes what a reviewer sees. Flag this as a known limit, not a silent one.
- Record alongside the paper: the form version or a content hash, the page draw settings (N, M) in force at attempt start, the seed, the algorithm id, and the time drawn. N and M at draw time matter because the authoring file can change later.
- The record is append-only in spirit: no code path rewrites a served paper after creation (do not "fix" a paper by redrawing). If a paper must be voided, mark the attempt, do not mutate the paper.
- Make the draw reproducible for review: given seed, algorithm id and the authored item list at the time, a reviewer could regenerate it, but only as a cross-check. See section 1: the stored list wins.
- Keep the draw deterministic with respect to authored order so content-sync (re-import of content files) does not reorder items under a stored paper. Stored papers should reference stable item identifiers, not positional indexes, and the spec should say what happens when a drawn question is deleted by a later content update (the paper still names it; the educator view for spec 4 must handle a missing item).

## 6. Summary of what this adds to the existing research

1. Store the resolved list as the truth; the seed is secondary because RNG algorithms are not version-stable. Record the algorithm id.
2. Use `secrets`-generated seeds, a local `Random` instance, sorted input, per-page sub-seeds, get-or-create under a uniqueness constraint.
3. Exposure is N/M per attempt; expected retake overlap is about N/M; M at least 2N is a sound warning threshold (inference, no published number).
4. Enforce "never expose undrawn" in one data-access function and in the answer-submit path, and audit counts and messages for leaks of pool size.
5. Extra validation: integer-only N, duplicate-text and M < 2N warnings, uniform group size with a useful error.
6. Audit record: paper plus seed, algorithm id, N and M at draw time, content version; no mutation; handle later-deleted questions.

## Sources

- [Python `random` docs](https://docs.python.org/3/library/random.html) (version-stability statement from memory of the docs; the fetch tool was not run on this page, so confirm wording before quoting)
- [NumPy compatibility policy](https://numpy.org/devdocs/reference/random/compatibility.html)
- [NumPy: Upgrading PCG64](https://numpy.org/devdocs/reference/random/upgrading-pcg64.html)
- [Scientific Python: NumPy RNG](https://blog.scientific-python.org/numpy/numpy-rng/)
- [ACT RR99-05: item exposure and pool size](https://act.org/content/dam/act/unsecured/documents/ACT_RR99-05.pdf)
- [A Review of Item Exposure Control Procedures](https://corpora.tika.apache.org/base/docs/govdocs1/477/477173.html)
- [JTLA exposure review](https://ejournals.bc.edu/ojs/index.php/jtla/article/viewFile/1647/1482)
- [Exposure control comparison, pool 100 vs 200](https://tdl-ir.tdl.org/signposting/describedby/f70c9e6a-01a9-4479-b9bd-70745b9d4543)
- [Moodle random question type](https://docs.moodle.org/en/Random_question_type)
- [Moodle forum: randomized questions repeating](https://moodle.org/mod/forum/discuss.php?d=236679)
- [EASA ECQB](https://www.easa.europa.eu/domains/aircrew-and-medical/european-central-question-bank-ecqb)
- [EASA Part-147 FAQ](https://www.easa.europa.eu/the-agency/faqs/part-147)
- [UK CAA GM 66.B.200 Examination by the CAA](https://regulatorylibrary.caa.co.uk/1321-2014/Content/AMC%20GM/GM%2066%20B%20200%20Examination%20by.htm)

status: ok
reason: Sourced where possible; pool-ratio, exposure-leak and audit-record points are labelled inference; Python `random` stability wording not fetched and flagged for confirmation.
