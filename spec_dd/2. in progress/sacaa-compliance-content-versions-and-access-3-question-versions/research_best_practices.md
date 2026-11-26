# Research: best practices for immutable question versions

Scope: stable `FormQuestion` identity, immutable version rows with a JSON option snapshot, pinning at attempt start, exact change detection, honest backfill, audit trail, read performance. Settled decisions are in `idea.md` and `answers.md` (pin in the served paper plus a nullable `QuestionAnswer` FK; reports out of scope). This file adds practice, not new scope.

Sourcing: items marked (web) came from searches this session (URLs at the end). Items marked (knowledge) are from general knowledge and the Django/PostgreSQL docs, and were not re-fetched here. Verify them while writing the spec.

## 1. Immutable, append-only rows

Practice is defence in depth, in three layers.

1. **Application layer (Django model).** Override `save()` to raise when `self.pk` already exists in the database (`self._state.adding` is False) and override `delete()` to raise. Do the same on a custom `QuerySet` or manager: `update()`, `delete()`, `bulk_update()` and `bulk_create(update_conflicts=True)` skip `save()` and `delete()`, so a guard on the model alone is not enough. (knowledge)
   - Give the version model a custom manager or queryset whose `update`/`delete` raise.
   - Cascades from `Collector` do not call `Model.delete()`. `on_delete=PROTECT` on the version's FK to `FormQuestion` prevents a cascade removing versions. (knowledge)
   - Put the only creating path in one function (for example `create_next_version(question)`) that `content_save` calls. Do not scatter `objects.create`.
2. **Database layer (PostgreSQL).** A `BEFORE UPDATE OR DELETE ... FOR EACH ROW` trigger whose function raises an exception makes the rule apply to every role, including the app role, and out-of-band SQL fails loudly (web: effaced hardening guide). Add a `BEFORE TRUNCATE ... FOR EACH STATEMENT` trigger too, because row-level triggers do not fire on TRUNCATE (knowledge, PostgreSQL trigger docs). Install with a `RunSQL` or `RunPython` migration, with reverse SQL, so it is reviewable and versioned. Pruning later means an explicit migration that drops the trigger, which makes retention a reviewed step (web).
   - Alternative or addition: `REVOKE UPDATE, DELETE, TRUNCATE` on the table from the app role. Stronger against the app, but the migration role usually owns the table and the test database setup is harder. Triggers are the simpler choice in a Django project that ships as an installable package. (knowledge)
   - The `danger_content_delete` development command wipes content tables. Decide explicitly whether the trigger blocks it (the likely right answer: it must delete versions in a controlled way, for example by disabling the trigger in that command only, or by running only on `DEBUG`).
3. **Detection layer.** Store a `content_hash` on each row so tampering by a superuser who can drop the trigger is detectable by recomputing. Hash chaining (each row's hash covers the previous row's hash) makes rewriting history visible; this is optional beyond the stated need and costs little (web: appmaster tamper-evident audit trails). The spec should say whether it wants chaining or just per-row hash.

Tests: a model test that `save()` on an existing row and `delete()` raise; a DB test that raw `UPDATE`/`DELETE`/`TRUNCATE` raise `InternalError`/`ProgrammingError` (needs `transaction=True` or a savepoint, because the failed statement aborts the transaction). (knowledge)

Note the unique constraint on (`question`, `number`) and a check that `number >= 1`. Allocate the number inside `transaction.atomic()` with `select_for_update()` on the `FormQuestion` row so two concurrent `content_save` runs cannot make duplicates; the unique constraint is the backstop. (knowledge)

## 2. Canonical serialisation and hashing

- Compare a canonical form, not the database JSON. `jsonb` normalises key order and whitespace on storage, so comparing the stored `jsonb` to a fresh Python dict by equality is fine, but hashing needs bytes you control. (knowledge)
- RFC 8785 (JCS) is the reference for canonical JSON: no insignificant whitespace, lexicographically sorted keys, deterministic string and number forms, I-JSON subset (web). It is Informational. For this project a simplified, documented rule is enough, and it only needs to be stable inside one codebase: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` encoded as UTF-8, then SHA-256. Record the rule and a `schema_version` in the snapshot so a later change to the field set is a known event rather than a spurious version. (knowledge)
- Pitfalls to design out:
  - **Floats and decimals.** JCS limits numbers to IEEE 754 doubles (web). `min`, `max` and option `value` should be serialised as strings or as `Decimal` rendered with a fixed format. Option `value` is already `str` in `content_save`.
  - **Unicode.** Normalise text to a single Unicode form (NFC) before hashing, or decide not to and say so. Without it, visually identical text can differ. Do not strip or trim whitespace silently: the idea says the comparison is exact, so a trailing space is a change. (knowledge)
  - **Ordering of options.** Order options by their `order` field and uuid for the snapshot, so a re-ordered YAML list that changes `order` is a change but row return order is not. Include option uuids so a replaced option with identical text is still a change.
  - **Null versus absent.** Always emit every versioned key, with `null` where empty, so absent and null do not hash differently across code versions.
  - **Hash what you store.** The idea recommends the stored, translated markdown. Build the snapshot from the saved database rows (after `save_with_uuid` finishes), not from the YAML, so the hash describes what learners were served.
- **Exact comparison is the source of truth; the hash is an index and an integrity check.** Compare the canonical bytes (or the canonical string) of the new snapshot with the latest version's stored canonical snapshot. A hash-only comparison is fine in practice, but the idea asks for exact comparison, so compare the snapshot and keep the hash as a quick filter and for audit. (knowledge)
- Unit-test the canonicaliser with golden vectors: same input in a different key order gives the same bytes; changing any one versioned field changes them; changing an unversioned field (`file_path`, `slug`, `tags`, `meta`, `updated_at`, page placement) does not.

## 3. JSON snapshot versus normalised version tables

- A JSON snapshot on the version row is the common choice for an audit record whose job is "what did this look like at time T": one row is a complete, self-contained fact, no joins, no second set of immutable tables, and a change to `QuestionOption` columns later does not rewrite history. Moodle's `question_versions` is the contrast: it keeps a stable `question_bank_entries` row and a version per `question` row, with options in per-type tables rewritten for each version (Moodle docs, prior art file). (knowledge; see also `research_question_versioning_prior_art.md`)
- Downsides to design for: no foreign key integrity from the snapshot to live option ids (a snapshot option id can dangle if an option is ever deleted; the repo never deletes options, and `QuestionAnswer.selected_options` is an M2M to the live `QuestionOption`, so keep option ids in the snapshot and keep options undeletable); schema evolution (carry `schema_version` and write a reader that tolerates old shapes); ad-hoc querying (use `jsonb` with a GIN index only if a query needs it; none is stated).
- Define the snapshot shape with a pydantic model (the repo already uses pydantic in `content_base`) and validate on write and on read. This also gives the "version exposes the same interface as a question" object: build lightweight dataclass-style objects (`id`, `question`, `type`, `options[]` with `id`, `text`, `value`, `order`, `correct`) from the validated model. (knowledge)
- Normalised option rows per version only pay off if options must be queried across versions (for example distractor statistics across all versions). That need is out of scope here because reports are out of scope.

## 4. Pinning in attempts

- Pin at the earliest moment the attempt's content is fixed, and in the same transaction that writes the attempt's served paper, so there is no window where a paper exists without pins. Read the latest versions with one query for the whole paper (`WHERE question_id IN (...)` ordered by `number DESC`, or a `latest` pointer), not one query per question. (knowledge)
- Pin by version id, not by "number at the time" or by timestamp. A timestamp pin ("the version live at start_time") is derivable but fragile around equal timestamps and clock changes; an id pin is exact and survives re-reads. (knowledge)
- Two stores agree by construction: the served paper's `versions` map and `QuestionAnswer.question_version`. Treat the paper as the source for what was served and the answer FK as the source for what was answered. Add a check or a test that an answer's version equals the pinned one for its question, and decide what the reader does if they disagree (fail loudly, since this is audit data).
- `QuestionAnswer.question_version` as `on_delete=PROTECT`, nullable only for rows that predate the migration or whose sitting has no pin; make the backfill fill them so the column is non-null in practice. (knowledge)
- Moodle pins the attempt to a `question_version` through `question_references`/`question_attempts` and shows the answered version in review, which is the same shape (prior art file).
- A stored `FormProgress.scores` stays frozen. Reading code should never silently fall back to the live row for a pinned attempt; a missing pin is an explicit "pre-version, content as migrated" state, not a fallback.
- Concurrency: an attempt that starts while `content_save` is mid-run must see either all of the new question versions or none for a given question. Wrap each question's version creation and live-row update in one `transaction.atomic()`; the paper builder reads inside its own transaction at default isolation and takes the latest committed version per question. A multi-question save is not atomic as a whole unless `content_save` wraps the whole run; say whether that is required.

## 5. Backfilling history honestly (data migration)

- Use `RunPython` with historical models (`apps.get_model`), a reverse function (a no-op or a delete that is allowed because the trigger is installed in a later migration), and batch with `iterator(chunk_size=...)` plus `bulk_create(batch_size=...)`. Order the migration: create the table, backfill version 1 and pin existing answers, then add the immutability trigger and tighten constraints, so the backfill does not fight the trigger. (knowledge; Django docs on data migrations)
- Be explicit in three places that version 1 is "the content as it stood when the migration ran", not the original wording: a `source` or `backfilled` field on the row (for example `origin = "migration_backfill"` versus `"content_save"`), the migration docstring, and the documentation. Give the backfilled row a `saved_at` equal to the migration time and `git_commit` null (content-save-safety's commit hash did not exist), rather than inventing values. An auditor then sees the limit in the data itself, not only in prose. (knowledge)
- Make the backfill idempotent and make first-run change detection consistent: the migration's version 1 uses the same canonicaliser and hash as `content_save`, so the first `content_save` after migration sees an equal snapshot and does not create version 2. Import the canonicaliser from application code at migration time is risky because the code may change later; a migration should embed a frozen copy of the function, with a test that the frozen copy and the live one agree on fixtures. (knowledge)
- Do not rewrite or recompute `FormProgress.scores`. Do not touch `asked` or `served_paper` beyond adding the `versions` key where the paper exists; leave old papers without the key and let the reader treat "no key" as "pinned by answer FK / migration version 1".

## 6. Audit-trail expectations (who, when, what, commit)

- Regulator-style audit records need: what changed (the snapshot and its predecessor), when (server-set timestamp, not client-supplied), who or what caused it, and where the content came from (commit hash). Record `saved_at` with `default=timezone.now` set in code once, plus the commit hash from content-save-safety, plus the `content_save` run identity if that spec provides one. "Who" is the operator running `content_save`; the idea does not require a user FK, so state in the spec that the commit is the authorship record, and add a nullable `saved_by` only if the access spec supplies a user at that point. (knowledge)
- Ensure `saved_at` cannot be edited: it is immutable with the rest of the row. `updated_at` on the version should not exist.
- Keep the previous version reachable: a unique (`question`, `number`) sequence with no gaps, and (optional) a `previous_hash` column for chaining (web: tamper-evident trails).
- Expose a read-only view of versions to the educator spec (5) rather than building audit UI here. This spec should make a query such as "all versions of question Q, with times and commits" trivial: an index on (`question`, `number`).
- Retire is separate; a revision never retires the question (settled).

## 7. Performance of reading versions for many attempts

- The unit of read is one attempt's paper: N questions, N pinned versions. Fetch with `QuestionVersion.objects.filter(id__in=pinned_ids)` in one query and build a dict, once per request, and attach it to `SittingPath`. Do not hit the version table per question or per option. (knowledge)
- Snapshots are `jsonb` and are TOASTed when large; a question with a handful of options is a few hundred bytes to a few KB, so it stays inline and is cheap. Use `.only()`/`defer()` if the snapshot is not needed (for example, listing versions by number and commit). (knowledge)
- For bulk readers (export, a later review list), group answers by version id and decode each distinct snapshot once; many attempts share few versions, so decoding is cached per version id (a per-request dict, or `functools.lru_cache` keyed on version id since rows are immutable, which makes caching safe by construction). (knowledge)
- Indexes: primary key on version id (the pin lookups); unique (`question`, `number`) serves "latest version of question" with `ORDER BY number DESC LIMIT 1`; consider `latest` lookup for `content_save` change detection at scale (one query per question; batch it with a `DISTINCT ON (question_id) ... ORDER BY question_id, number DESC` which Django supports on PostgreSQL via `.order_by(...).distinct("question_id")`). (knowledge)
- Storing the answered version FK on `QuestionAnswer` adds one indexed column; no join is needed on the hot path if the version is looked up by id.
- Run `django-debug-toolbar`/`assertNumQueries` tests: results page, export and admin answer views should have a constant query count independent of the number of questions (a regression test, since an N+1 on "the pinned version of each answer" is the likely mistake).

## 8. Checklist for the spec

1. Immutable at model, queryset and DB (UPDATE, DELETE, TRUNCATE trigger) level, with tests at each level.
2. A single creation function inside a transaction with a lock on the question and a unique (`question`, `number`).
3. A documented canonical form with `schema_version`, fixed numbers as strings, NFC decision, and golden-vector tests; exact comparison of canonical snapshot, hash as an integrity field.
4. Snapshot validated by pydantic, includes live option ids; version-backed objects with the same interface as `FormQuestion` / `QuestionOption`.
5. Pin by id in the same transaction as the served paper; the answer FK agrees; a missing pin is an explicit state, never a silent live-row fallback.
6. Backfill with an `origin` marker, null commit, a frozen canonicaliser copy, idempotent first-run detection, scores untouched.
7. Constant-query reads of pinned versions; per-request or per-version cache.
8. Decide on `danger_content_delete` against the trigger, and on hash chaining.

## Reference URLs

- Hardening an audit trail with a raising BEFORE UPDATE OR DELETE trigger (web): https://jaylann.github.io/effaced/docs/guides/audit-hardening/
- Tamper-evident audit trails in PostgreSQL, hash chaining (web): https://appmaster.io/blog/tamper-evident-audit-trails-postgresql
- PostgreSQL PL/pgSQL trigger procedures (web): https://www.postgresql.org/docs/17/plpgsql-trigger.html
- RFC 8785 JSON Canonicalization Scheme (web): https://www.rfc-editor.org/rfc/rfc8785
- RFC 8785 info page and errata (web): https://rfc-editor.org/info/rfc8785 , https://www.rfc-editor.org/rfc/beta/errata/rfc8785.html
- Django data migrations (knowledge, not fetched): https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations
- Django `QuerySet.distinct` with fields on PostgreSQL (knowledge, not fetched): https://docs.djangoproject.com/en/stable/ref/models/querysets/#distinct
- Local prior art (Moodle, Canvas, Open edX, Questionmark): `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md`

status: ok
