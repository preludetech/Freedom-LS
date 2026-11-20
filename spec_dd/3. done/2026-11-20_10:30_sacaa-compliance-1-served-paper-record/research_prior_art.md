# Research: prior art for a per-attempt served-paper record

Question: what has already been tried for per-attempt served-paper records, in this repo or
elsewhere, and what happened? Read at HEAD 53fb74dfe. Builds on the seams, SACAA and randomisation
research; it does not repeat them.

## 1. Earlier attempts in this repo

Three earlier efforts aimed at this record. None reached a spec or any code.
`git log --all -S shuffle -- freedom_ls` finds nothing related, and no branch has commits beyond
its spec files.

| When | What | Where it went |
|---|---|---|
| 2026-04-24 | `SACAA functionality audit/` (requirements text, matrix, gap analysis) plus the idea `00. sacaa-exam-audit-log`: an append-only `ExamAttempt` / `ExamAttemptQuestion` pair written at submission, holding **copies** of question text, options and identity, a SHA-256 hash, a Postgres trigger blocking UPDATE/DELETE, and no FK into the live form (commit a77963cfb) | Deleted the next day (e7875eb58) and replaced by `content_snapshots`. The audit folder was deleted in the 2026-04-26 cleanup (49e2e191d). |
| 2026-04-25 | `content_snapshots`: a generic app for immutable, hashed snapshots of content objects, with no consumer | Spent seven months "in progress" with only "write the idea" ticked, then paused on 2026-11-12 (81a0a94e6). Branch `content_snapshots` has no code. |
| 2026-06-30 | `compliance-form-randomization`: all four randomisation knobs in one idea, with `shuffle_seed` plus `realized_order` on `FormProgress` (`research_randomization_ux_integrity.md` 3.2 and 6.4) and a separate `QuizAttemptDraw` model (`sacaa-compliance-3-question-pools/research_question_bank_patterns.md` 5.2) | Moved to in progress on 2026-07-01 (acf98f4c7) and never specced. It was paused, then cut into the four `sacaa-compliance-*` specs on 2026-11-17 (585efd5f1). |

What happened, and what it means for this spec:

- The frozen-copy design stalled twice: first when it was scoped to one consumer, then when it was
  made generic. This idea instead stores references to the live rows and leaves frozen text to
  `content_snapshots`. That is the scope that has a chance of shipping. Keep it.
- The two paused research files disagree on the shape of the record: a JSON field on
  `FormProgress` against a separate model. They also disagree on the seed. The randomisation
  research wants a seed. The bank research (2.4, 5.6) says storing the full resolved list makes a
  seed unnecessary. This spec settles both. Since the record stores the realised order, the seed is
  only provenance. If the spec keeps one, it should be nullable for legacy attempts, and nothing
  should read it to rebuild an order.
- The randomisation research also proposed `shuffle_seed = UUIDField(default=uuid.uuid4)`. A
  default like that gives every existing row a made-up seed when the migration runs, which falsely
  implies those attempts were shuffled. Use null for "no record" instead.

## 2. The April SACAA text is missing from the current research

The deleted `SACAA functionality audit/sacaa-requirements.md` reproduces "141.07.1 Requirements
relating to training, 1. E-Learning system" with a risk matrix (Cat 1 to 5). The current
`research_sacaa_requirements.md` did not find it. It says "no regulation or SA-CATS text found
stating CBT system technical requirements" and names an unread "e-learning platform risk matrix"
document. The April text says:

- Assessment row: Cat 2 is "random questions from master list or randomized question and answer
  order", and Cat 3 and Cat 4 are "random questions (and answers) from master list".
- 1(c): "exam records shall be maintained and shall not be able to be deleted or manipulated".
- 1(d): moderation may award marks for a defective question, but "the marks on the system cannot
  be manipulated".
- 1(e): "whenever a question is revised it shall be blocked from the random questions ... but,
  should remain in the system for audit purposes".
- Record keeping is "Audit trail" at Cat 2 and "All data kept for 5 years" at Cat 3 and above.

The repo does not record where this text came from (it is likely SA-CATS 141), and it has not been
checked against an official copy. If it holds, three things follow:

- The roadmap's assumption that "no SACAA text found mandates a randomisation mechanic" is wrong
  for Cat 2 and above. That is the effort's business, not this spec's.
- For this spec, 1(c) and 1(d) pull against the decision in `answers.md` to "skip deleted items on
  read and shrink `max_score`". **Recommendation:** the stored record never drops an id. Skipping
  happens only when the record is read. A completed attempt's stored `scores` is never rewritten.
  The learner results "outdated score" check must also not report a deletion as an outdated score,
  or it nudges someone to "fix" a mark the rule says must not change. This applies the answer
  rather than reversing it. The paper stays complete as a list of ids even after a live row is
  gone.
- 1(e) suggests that revising a question should become a new row (new uuid) rather than an edit
  in place. That is `content_snapshots` or later work. Put it in "Out of scope" with this citation
  so it is not lost.

Add a todo for the user: confirm the source and status of the 141.07.1 text before the effort
relies on it.

## 3. The nearest shipped precedent: `FormProgress.asked` (form-engine-branch-logic, done 2026-11-06)

The old roadmap said the branch-logic spec and `compliance-form-randomization` would share a
per-attempt record, and that "whichever lands first designs it for both" (quoted in
`3. done/2026-11-06_12:46_form-engine-branch-logic/research_prior_art.md:48-50`). Branch logic
landed first. Its record does not cover what this spec needs:

- `asked` is written **at completion**, not at start (`models.py` `complete()`, spec lines 113-119).
  It is null while the attempt is in progress, and the spec chose on purpose that an in-progress
  attempt "is evaluated against the current form". This spec reverses that for quizzes: the paper
  freezes when the attempt starts. Say so explicitly, since the old decision is written in a done
  spec.
- `asked` is a set in practice. `frozen_path` (`conditions.py:231-244`) turns its lists into sets
  and walks `form.pages.all()` in authored order, so the order of the stored lists is ignored. It
  also stores no option order. Ordered output therefore cannot be added just by writing `asked` in
  a different order.
- The spec has to decide how the new record relates to `asked`. For a quiz they describe the same
  set, because quizzes cannot use `when`. Options:
  (a) keep writing `asked` at `complete()` and have the readers prefer the new record;
  (b) build `asked` from the record at completion;
  (c) replace `asked` for quizzes.
  Option (a) or (b) is the least disruptive. `asked` already has readers: the read-only admin
  field, `answer_groups` and `exports.off_path_question_ids`. Whichever option is chosen, write
  down the precedence in `sitting_path`. Today the order is `asked`, then `full_path` for a
  completed attempt, then `compute_path` (`conditions.py:254-266`). The new record has to fit into
  that order.
- Precedents worth reusing:
  - Legacy fallback: a completed attempt with `asked` null reads as "asked everything" (it uses
    `full_path`). The spec's rule that an attempt with no record falls back to authored order
    follows the same pattern. It also covers in-flight attempts until the lazy write runs.
  - Skip on read: `frozen_path` already drops ids that are no longer in the live tree, because it
    filters the current tree by id. The answer "skip deleted items on read" is therefore existing
    behaviour, not new risk.
  - Clamping a stale number: `resume_page_number` already clamps `furthest_page_reached` because
    it "outlives a page an author later deletes" (`paging.py:57-76`). Moving it to served positions
    should keep that clamp.
  - QA seeders: branch logic had to make its seeders finish attempts through `complete()` (commit
    5353c899a). Several `qa_helpers` commands create `FormProgress` rows directly
    (`qa_create_phone_question_scenario.py:183`, `qa_create_bulk_applications.py:95`,
    `qa_create_second_application_form_course.py:142`). A lazy write on read covers those rows
    without changes, which is another reason to write lazily rather than at creation.

## 4. Facts from the code that the spec relies on

- Attempts are created in two places: `learner_progress/attempts.py:94`
  (`get_or_create_incomplete`, inside `transaction.atomic`) and `course_applications/views.py:119`
  (under `select_for_update`). The lazy write can race on two concurrent first requests, and the
  application code already locks for exactly that reason. Make the write conditional, for example
  an `UPDATE ... WHERE record IS NULL` followed by a re-read, so the second request reads the first
  request's paper instead of overwriting it.
- Reference stability: `content_save` writes option uuids back into the YAML on first import
  (`content_save.py:774-780`), and pages, questions and content blocks carry `uuid` in the files. A
  re-import keeps the same ids, so a record of string uuids, in the same style as `asked`, survives
  edits.
- Deletion paths: `content_save` never deletes form rows. The only `.delete()` in that command is
  for due dates (`:1258`), and its own comment says stale rows stay. Removing a page, question or
  option therefore happens only through the admin, or through `danger_content_delete` on the whole
  form, which `FormProgress.form` (PROTECT) blocks once an attempt exists. `QuestionAnswer.question`
  is PROTECT, so a deleted served question is always an **unanswered** one, and option rows cascade
  with it. That keeps the "skip on read" cases narrow: admin-deleted pages, unanswered questions
  and options. The tests can target exactly those three.
- Stale rows are still served. A question removed from the YAML stays attached to its page and is
  still rendered, so the record will faithfully capture stale content. That is an existing
  content-import gap, not this spec's to fix. Mention it so no reviewer blames the record.

## 5. Elsewhere

- Moodle persists the resolved attempt when it starts and reuses it on resume: one
  `question_attempts` row per slot, with a `layout` column on `quiz_attempts`. The drawn question is
  stored as step data, and multichoice keeps its choice order as `_order` in step data. A redraw
  happens only on a new attempt.
  Sources: [Random question type](https://docs.moodle.org/502/en/Random_question_type),
  [quiz_attempts schema](https://moodleschema.zoola.io/tables/quiz_attempts.html),
  [MDL-45686 (`_order` in multichoice step data)](https://tracker-old.moodle.org/browse/MDL-45686).
  This matches the idea's choice of an order stored explicitly at start, with options included.
- Moodle does not truly delete a question that attempts use. It hides the question, "since they are
  necessary to give meaning to existing quiz attempts"
  ([forum, Tim Hunt](https://moodle.org/mod/forum/discuss.php?d=438090)). An edit made during an
  ongoing attempt does not reach that attempt, even with "Always latest"
  ([MDL-80006](https://tracker-old.moodle.org/browse/MDL-80006)). Bug reports show the
  version-pinning behaviour has been inconsistent across 4.x
  ([MDL-74255](https://tracker-old.moodle.org/browse/MDL-74255)). The lesson is that a frozen paper
  pointing at mutable rows is the hard part. FLS accepts live references here (the idea's "Out of
  scope"), which is consistent with deferring to `content_snapshots`.
- In Articulate Storyline under SCORM, some LMSs redraw on resume instead of restoring the original
  draw, a known correctness bug (`research_question_bank_patterns.md` 1.3). The spec's resume test
  ("a refresh or resume shows the same paper") is the guard against that bug. Keep it as a success
  criterion.

## 6. What changes the spec

1. Store the record as ids only and never prune it. Skip missing items only on read. Never rewrite
   the stored `scores` of a completed attempt, and do not let the outdated-score check report a
   deletion. This reconciles `answers.md` with SACAA 1(c) and 1(d).
2. Define how the record relates to `asked` and the new precedence in `sitting_path`. State that
   quizzes now freeze the paper at start, which reverses the branch-logic decision for them.
3. Make the seed nullable and provenance only, with no `uuid4` default. Nothing reads it to rebuild
   an order.
4. Make the lazy write idempotent under concurrent first requests, using a conditional update. It
   covers both creation sites and the `qa_helpers` rows.
5. Test the skip-on-read cases against the deletions that can actually happen: admin page delete,
   unanswered question delete, option delete.
6. Add a user todo to verify the provenance of the 141.07.1 e-learning text. Note that question
   revision as a new version (1(e)) is out of scope and cite it.

status: ok
