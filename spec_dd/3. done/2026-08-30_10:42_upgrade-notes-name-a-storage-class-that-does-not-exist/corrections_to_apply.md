# Corrections to apply to `prod_bucket_setup/upgrade_notes.md`

The row-by-row correction list `1. spec.md` §Requirements B works from. Where this file and
`research_upgrade_notes_claim_audit.md` disagree, this one wins: every claim here was re-derived from
the code rather than carried over.

Verified against HEAD of this branch. Every claim below was independently re-derived from
`freedom_ls/deployment/checks.py`, `freedom_ls/deployment/storage.py`, `freedom_ls/base/storage.py`,
`config/settings_base.py`/`config/settings_prod.py`, the `storage=` usages across `freedom_ls/**/models.py`,
`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/env_example`, and
`claude_plugins/fls-dev/skills/file-storage/SKILL.md` — not trusted from the audit's citations alone. One
audit citation error was found and is called out in the table (#8).

All line numbers for `upgrade_notes.md` refer to
`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/upgrade_notes.md` (116 lines) as it stands today.

## 1. Verified defect table

| # | Line(s) | Quoted text | Shipped code says | Replacement / constraint | Verification |
|---|---|---|---|---|---|
| 0 | 90–93 | "...including the `public` entry, which uses `freedom_ls.deployment.storage.OverwritingFileSystemStorage` rather than the stock backend so a replaced organisation logo overwrites its stable `organisations/{pk}{ext}` key locally the way it does on S3." | No `OverwritingFileSystemStorage` class exists anywhere in the codebase. The `public` entry in `settings_base.py` is the stock `django.core.files.storage.FileSystemStorage` with `"OPTIONS": {"allow_overwrite": True}`. | Replace the class reference with: `django.core.files.storage.FileSystemStorage` with `"OPTIONS": {"allow_overwrite": True}`. This must also fix line 87's "no `OPTIONS` key" instruction (see #7 below) since the two clauses describe the same entry and currently contradict each other. | `grep -r OverwritingFileSystemStorage freedom_ls/` — zero hits in application code (only in this spec's own idea/research docs). `config/settings_base.py:284-287` shows the actual entry. |
| 1 | 42–50 | "`manage.py check --deploy` gains two errors. `freedom_ls_deployment.E001`... `freedom_ls_deployment.E002`... Both checks are `deploy=True`" | Four checks exist, all `@register(Tags.security, deploy=True)`: E001 (alias shares default's bucket), E002 (alias on local disk while `DEBUG=False`), E003 (alias inherited its bucket from the shared `AWS_STORAGE_BUCKET_NAME`), E004 (a signed-URL-required alias serves unsigned URLs). | State all four with the same E001/E002 prose plus new paragraphs for E003 and E004, and change "gains two errors" to "gains four errors." | `freedom_ls/deployment/checks.py:1-27` (module docstring), `:113-178` (E001), `:181-221` (E002), `:224-270` (E003), `:273-314` (E004). All four decorated identically at lines 113, 181, 224, 273. |
| 2 | 46–47 | "Keep only the shared `AWS_STORAGE_BUCKET_NAME` set and all five media aliases resolve where `default` does: five E001 errors, one per alias." | Independently traced `check_media_aliases_not_shared_with_default` and `check_media_aliases_name_their_own_bucket` against this exact scenario: with only the shared var set, every media alias *and* `default` resolve to the same S3 identity (bucket from `AWS_STORAGE_BUCKET_NAME`) → 5 × E001 fires (identity == default_identity). Independently, `bucket_name_for(purpose)` returns `(shared_bucket, from_shared=True)` for every alias, and `identity[1] == bucket` holds for all 5 → E003 also fires once per alias. Total: **10 errors** (5×E001 + 5×E003), not 5. E004 does not fire in this scenario (default `AWS_QUERYSTRING_AUTH` resolves `True`). | State: "...that configuration fires ten errors: five `E001` (each alias matches `default`'s bucket) and five `E003` (each alias inherited that bucket from the shared variable), one pair per alias." | Traced `checks.py:140-178` (E001) and `:245-270` (E003) against `storage.py:67-76` (`bucket_name_for`) and `:104-137` (`_alias_entry`) line by line for this exact input state. |
| 2b | 47–48 | "Set no `AWS_*` variable at all and every alias drops to local disk instead: five E002 errors." | Verified accurate. With no bucket resolvable, `_alias_entry` returns `FileSystemStorage` for every alias; E001 and E003 both skip filesystem identities (`identity[0]=='fs': continue` and `not bucket: continue` respectively); E004 only inspects `S3Storage` instances. Only E002 fires, once per media alias (5). | No change needed — leave as written. | `storage.py:104-116` (`_alias_entry`, bucket falsy branch), `checks.py:166,209,248` (the three skip conditions). |
| 3 | 11 | "`SILENCED_SYSTEM_CHECKS` # optional: drop any `freedom_ls_reports.W001` entry, `freedom_ls_deployment.E002` is silenceable" | Incomplete: E001, E003 and E004 are equally ordinary `Tags.security` checks and equally silenceable — nothing special-cases E002. | Either drop the E002-specific claim, or extend it: "`freedom_ls_deployment.E001`/`E002`/`E003`/`E004` are all silenceable like any Django check id." | `checks.py:113,181,224,273` — identical `@register(Tags.security, deploy=True)` decorator on all four, no differentiated silencing logic anywhere in the file. |
| 4 | 7 | "`STORAGES` # hard: all five media aliases must be declared or model import raises `InvalidStorageError`" | Contradicted by the document's own body two lines below (line 31): only 3 of 5 aliases are bound to a model field today (`public`, `course_media`, `reports`) and fail at import; `user_uploads` and `certificates` have no field, so an undeclared one of those surfaces only as `E001` under `check --deploy`. | "`STORAGES` # hard: `public`, `course_media` and `reports` must be declared or model import raises `ImproperlyConfigured`; `user_uploads` and `certificates` have no bound field yet and surface as `E001` instead." | Grepped every `**/models.py` for `storage=`: `freedom_ls/organisations/models.py:70,81` (`public`, both `logo` and `logo_on_dark`), `freedom_ls/content_engine/models/files.py:41` (`course_media`), `freedom_ls/reports/models.py:72` (`reports`). No other `models.py` file names a `storage=` callable. |
| 5 | 29–30 | "A callable `storage=` runs once, at model import, so an alias your settings module does not declare raises `InvalidStorageError` while Django is importing models." | The exception actually raised is `django.core.exceptions.ImproperlyConfigured`, not `InvalidStorageError`. `storage_for_alias()` catches `InvalidStorageError` internally and re-raises `ImproperlyConfigured` with the alias name and the setting that chose it. | "...raises `ImproperlyConfigured` (naming the missing alias and the setting that chose it) while Django is importing models." | `freedom_ls/base/storage.py:7-23` — `try: return storages[alias] except InvalidStorageError as err: raise ImproperlyConfigured(...) from err`. All three `storage=` callables (`get_organisation_logo_storage`, `get_content_media_storage`, `get_reports_storage`) route through this function. |
| 6 | 21 | "FLS media no longer lives in one bucket. Six `STORAGES` aliases now resolve independently..." | Ambiguous, not false: "six" only holds under the `default` + 5-media-aliases convention (excludes `staticfiles`), which is a real, named convention elsewhere (`claude_plugins/fls-dev/skills/file-storage/SKILL.md:9,34` says "six `STORAGES` aliases" / "The six aliases" explicitly). But `upgrade_notes.md` never defines this convention and uses "five" for the same set everywhere else in the document (lines 7, 33, 46–47, 108–109). | Either define the convention on first use ("six aliases — `default` plus the five media aliases — excluding `staticfiles`") or drop "six" here and say "five media aliases plus `default`" to match the rest of the document's own usage. | `storage.py:48-64` (`media_alias_purposes()` returns exactly 5 entries); `SKILL.md:9,34` (confirmed the "six" convention is real and named there, just not in this document). |
| 7 | 23 | "In production those six aliases sit on three buckets." | Wrong under every reading. Even granting "six" = `default` + 5 media (the only defensible reading, per #6), `default`'s value (`AWS_S3_DEFAULT_BUCKET_NAME`, e.g. `fls-prod-default`) is explicitly *not* one of the three real buckets — it is a fourth, deliberately-nonexistent placeholder value ("no bucket is created behind this name. Nothing should ever write here"). | "Five of those aliases sit on three real buckets in production; `default` resolves to a fourth, deliberately nonexistent bucket name that nothing should ever write to." | `env_example:116-119` (comment on `AWS_S3_DEFAULT_BUCKET_NAME`) and `env_example:86` ("Six name variables, four values, three real buckets"). `storage.py` treats `DEFAULT_PURPOSE` through the identical `_alias_entry()` path as the 5 media purposes but it is not a member of `media_alias_purposes()`. |
| 8 | 52 | "Five per-bucket variables do not mean five new buckets." | Wrong, and self-contradictory two sentences later in the same paragraph (line 54: "Three buckets, **six** variables") and again at Manual step 5 (line 101: "Set all **six** bucket-name variables"). The correct count is six: `AWS_S3_PUBLIC_BUCKET_NAME`, `AWS_S3_CERTIFICATES_BUCKET_NAME`, `AWS_S3_COURSE_MEDIA_BUCKET_NAME`, `AWS_S3_GENERATED_BUCKET_NAME`, `AWS_S3_USER_UPLOADS_BUCKET_NAME`, `AWS_S3_DEFAULT_BUCKET_NAME`. **Audit citation correction:** the audit cites the six `*_PURPOSE` constants at `freedom_ls/deployment/config.py:18-23` — that file has no `*_PURPOSE` constants at all (it only holds `DeploymentSettings`/Sentry/PostHog settings). The six constants (`LOGO_PURPOSE`, `CONTENT_MEDIA_PURPOSE`, `USER_UPLOADS_PURPOSE`, `CERTIFICATES_PURPOSE`, `REPORTS_PURPOSE`, `DEFAULT_PURPOSE`) are actually at `freedom_ls/deployment/storage.py:18-23`. The underlying claim (six variables) is correct; only the audit's file citation is wrong. | "Six per-bucket variables do not mean six new buckets." | `freedom_ls/deployment/storage.py:18-23` (six `*_PURPOSE` constants — **not** `config.py`); `env_example:106-119` (the six `AWS_S3_*_BUCKET_NAME` lines, verbatim). |
| 9 | 87 | "Declare the six aliases in your base or development settings too, pointing every one at the stock `FileSystemStorage` with no `OPTIONS` key." | Self-contradicting within its own sentence/paragraph: the very next clause (lines 90-93) describes the `public` entry's `OPTIONS` key (`allow_overwrite`). The "no `OPTIONS` key" instruction is also simply wrong as a blanket rule — `public` always needs `OPTIONS: {"allow_overwrite": True}`, in dev/test settings just as much as in prod. | "...pointing every one at the stock `FileSystemStorage`, except `public`, which needs `OPTIONS: {"allow_overwrite": True}` so a replaced logo overwrites its stable key locally the way it does on S3 — see `config/settings_base.py`'s `STORAGES` dict for the exact shape." | `config/settings_base.py:284-293` — the base/dev `STORAGES` dict has exactly one `OPTIONS` key, on the `public`/`ORGANISATION_LOGO_STORAGE_ALIAS` entry; every other alias (`course_media`, `user_uploads`, `reports`, `certificates`) has none. |
| 10 | 108–109 | "it reaches all five media aliases, two of which hold personal data" | Accurate as written, but should note the check that now backs it: `freedom_ls_deployment.E004` (new, undocumented elsewhere in the file — see #1) exists specifically to catch a signed-URL-required alias serving unsigned URLs, for the 3 aliases in `SIGNED_URL_PURPOSES` (`course_media`, `user_uploads`, `reports`), a superset of the "two ... personal data" aliases named here. | No change to this sentence itself; add a note that `check --deploy` (E004) also catches this misconfiguration, so the manual step is defence-in-depth, not the only guard. | `storage.py:28-30` (`SIGNED_URL_PURPOSES = frozenset({CONTENT_MEDIA_PURPOSE, USER_UPLOADS_PURPOSE, REPORTS_PURPOSE})`); `checks.py:273-314` (E004). |
| 11 | 111–112 | "Add `manage.py check --deploy` to your deploy pipeline if it is not there already. Nothing else runs E001 or E002." | Literally true but incomplete — nothing else runs E003 or E004 either, and both are silent outside `check --deploy` for the same reason. | "Nothing else runs E001, E002, E003 or E004." | `checks.py:113,181,224,273` — all four `deploy=True`. |

Row 0 and rows 1–11 above are the eleven defects named in the task prompt: 0=OverwritingFileSystemStorage,
1=missing E003/E004 coverage + wrong overall error count claim, 2=wrong error counts for the documented
upgrade scenario, 3=SILENCED_SYSTEM_CHECKS singling out E002, 4=frontmatter "all five" vs the three that
actually fail at import, 5=InvalidStorageError vs ImproperlyConfigured, 6=six-vs-five alias convention,
7="six aliases on three buckets" arithmetic, 8=five-vs-six variable self-contradiction, 9=the "no OPTIONS
key" instruction contradicting itself, 10=E004 not connected to the manual QUERYSTRING_AUTH step, 11=E003/E004
omitted from "nothing else runs E001 or E002."

### Claims the audit table did not flag but that need a look during rewrite

- **Migration 0004** (`freedom_ls/organisations/migrations/0004_organisation_logo_on_dark_alter_organisation_logo_and_more.py`) adds `Organisation.logo_on_dark`, also with `storage=get_organisation_logo_storage`, dated one day after 0003. `upgrade_notes.md` Manual step 1 says "Two `AlterField` migrations record the new `storage=` callables" — this remains literally true (0004 is a separate `AddField`+`AlterField`, not a third migration newly introducing a `storage=` callable), so it is **not a defect**, just worth a human decision on whether 0004 belongs in scope for this document at all. Not something the rewrite is required to touch.

## 2. The correct numbers

**Aliases (7 `STORAGES` keys total):** `default`, `staticfiles`, `public`, `course_media`, `user_uploads`,
`reports`, `certificates`. Confirmed against `config/settings_base.py:281-294` (7-entry dict) and
`freedom_ls/deployment/storage.py:140-163` (`build_storages()` returns the same 7 keys — 5 media entries via
`media_alias_purposes()`, plus `storages["default"]` and `storages["staticfiles"]` set explicitly).

- **Media aliases (5):** `public`, `course_media`, `user_uploads`, `reports`, `certificates` —
  `storage.py:48-64`.
- **Static:** `staticfiles` — always the project's own static backend, never resolved from `AWS_*`
  (`storage.py:140-163`, `settings_base.py:283`).
- **"Six" (a real, separately-used convention):** `default` + the 5 media aliases, i.e. every key except
  `staticfiles`. Used explicitly by `claude_plugins/fls-dev/skills/file-storage/SKILL.md:9,34` and by
  `env_example:86` ("Six name variables"). `upgrade_notes.md` should either define this convention on first
  use or stop mixing it with the "five" convention it uses everywhere else.
- **Public-facing (anonymous read) vs private (signed URLs):** `public`, `certificates` are meant to be
  anonymously readable (branding bucket); `course_media`, `user_uploads`, `reports` are the
  `SIGNED_URL_PURPOSES` set that must never serve unsigned URLs (`storage.py:28-30`). `user_uploads` and
  `reports` additionally hold personal data; `course_media` does not (`SKILL.md:23-27`).

**Buckets:** 3 real buckets in production. `public` and `certificates` share the branding bucket;
`reports` and `user_uploads` share the learner-data bucket; `course_media` has its own. `default`'s bucket
name is a 4th, deliberately nonexistent placeholder value — "no bucket is created behind this name"
(`env_example:107-119`).

**Per-bucket environment variables (6, one per purpose, not 5):**
`AWS_S3_PUBLIC_BUCKET_NAME`, `AWS_S3_CERTIFICATES_BUCKET_NAME`, `AWS_S3_COURSE_MEDIA_BUCKET_NAME`,
`AWS_S3_GENERATED_BUCKET_NAME` (this is the `reports` alias's purpose — the env var name is `GENERATED`,
not `REPORTS`), `AWS_S3_USER_UPLOADS_BUCKET_NAME`, `AWS_S3_DEFAULT_BUCKET_NAME`. Source of truth: the six
`*_PURPOSE` constants at `freedom_ls/deployment/storage.py:18-23` (`LOGO_PURPOSE="PUBLIC"`,
`CONTENT_MEDIA_PURPOSE="COURSE_MEDIA"`, `USER_UPLOADS_PURPOSE="USER_UPLOADS"`,
`CERTIFICATES_PURPOSE="CERTIFICATES"`, `REPORTS_PURPOSE="GENERATED"`, `DEFAULT_PURPOSE="DEFAULT"`), each
plugged into the `AWS_S3_<PURPOSE>_BUCKET_NAME` pattern by `bucket_name_for()` (`storage.py:67-76`), and
verbatim in `env_example:106-119`.

**System check errors on a first `manage.py check --deploy`, per alias — traced against
`freedom_ls/deployment/checks.py`, not asserted:**

This is not one number; it depends on the starting env state, and the document should say so rather than
assert a single count. Three states matter and were each traced line-by-line against `checks.py`:

1. **Fresh checkout, no `AWS_*` variable set at all** (a plausible first `check --deploy` after a clean
   install): every media alias's `_alias_entry()` falls to `FileSystemStorage` (`storage.py:112-116`);
   E001 and E003 both explicitly skip filesystem identities (`checks.py:166`, `:248`); E004 only inspects
   `S3Storage` instances (`checks.py:298`). Result: **5 errors, all `E002`**, one per media alias. Matches
   what the document already says (accurate, no change needed).
2. **Migrating from the old single-bucket layout — only the shared `AWS_STORAGE_BUCKET_NAME` set**
   (the scenario `upgrade_notes.md` line 46 actually describes, and the realistic "day one of this upgrade"
   state for an existing project): every media alias and `default` resolve to the same S3 identity, so
   `identity == default_identity` for all 5 → **5×E001**; independently, each alias's `bucket_name_for()`
   reports `from_shared=True` and its resolved bucket matches the shared value → **5×E003**. E004 does not
   fire (default `AWS_QUERYSTRING_AUTH` resolves `True`). Result: **10 errors** (5 E001 + 5 E003), not 5.
   This is the number the document gets wrong (see defect #2).
3. **Fully correct end state per Manual steps 1–8** (all six `*_BUCKET_NAME` vars set to their real
   values, shared `AWS_STORAGE_BUCKET_NAME` left unset, per-alias `QUERYSTRING_AUTH=false` set only for
   `public`/`certificates`): every media alias's own bucket-name var is set, so `from_shared=False` for all
   5 → E003 never fires; each alias's bucket differs from `default`'s (`fls-prod-default`) → E001 never
   fires; nothing is on local disk → E002 never fires; the 3 `SIGNED_URL_PURPOSES` aliases keep the shared
   `AWS_QUERYSTRING_AUTH=True` default → E004 never fires. Result: **0 errors** — a downstream that follows
   every manual step correctly reaches a genuinely clean `check --deploy`. The document currently never
   states this end state explicitly; it should, since it is the one number that *can* be asserted
   unconditionally and gives the reader something to converge on.

The document should present states 2 (realistic starting point) and 3 (correct end state) explicitly,
rather than a single blanket "gains N errors" claim — the count is a function of which per-bucket variables
are set, not a fixed property of the upgrade.

## 3. The `env_example` path defect

Manual step 5 (line 105) cites `spec_dd/2. in progress/prod_bucket_setup/env_example`. That path does not
exist. The file is at **`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/env_example`** (confirmed to
exist and readable — 169 lines).

Two separate things changed between when the notes were written and now, not one:

1. **Stage directory**: `2. in progress/` → `3. done/`, the standard move every spec undergoes on
   completion.
2. **Directory name**: `prod_bucket_setup` → `2026-08-27_12:32_prod_bucket_setup`. Every completed spec
   under `spec_dd/3. done/` carries a `YYYY-MM-DD_HH:MM_` prefix (confirmed by listing all 21 directories
   there); in-progress specs do not. So the cited path was correct as written at the time — both segments
   — and was invalidated by the same act (spec closure), not by an independent later rename.

**Content check:** the file at the corrected path already reflects the shipped reality more accurately
than `upgrade_notes.md` does — it documents all four checks (E001/E002/E003/E004 all named explicitly at
`env_example:97-103,149-150`), the six bucket-name variables, and "three real buckets" with the `default`
caveat spelled out. `env_example` is not itself stale in the way `upgrade_notes.md` is; only the citation to
it is broken. The fix for step 5 is a path-only edit:
`spec_dd/2. in progress/prod_bucket_setup/env_example` → `spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/env_example`.

## 4. Claims that check out — do not touch

- `Organisation.logo`, `content_engine.File.file`, `GeneratedReport.file` each pass a `storage=` callable
  (organisations/models.py:70,81; content_engine/models/files.py:41; reports/models.py:72).
- The three aliases with a bound field today are `public`, `course_media`, `reports`; `user_uploads` and
  `certificates` have none.
- "Declare all five, alongside `default` and `staticfiles`" (7 total keys) — matches the shipped
  `STORAGES` dict exactly.
- The reports storage fallback to `default` is gone — no try/except in `get_reports_storage()`.
- E001's and E002's individual definitions (not their exhaustiveness) match `checks.py`'s docstrings
  exactly.
- "Both checks are `deploy=True`" — true (also true of E003/E004, just not mentioned).
- "five E002 errors" when no `AWS_*` var is set at all — verified independently above (state 1).
- "public and certificates both point at the anonymously readable branding bucket, and reports and
  user_uploads both point at the learner-data bucket" — matches `env_example`.
- `report_upload_path` returns `cohort_reports/{pk}-cohort-report.pdf`, distinct from `user_uploads/` —
  matches `reports/models.py`.
- `freedom_ls_reports.W001` is gone outright; the id is not held in reserve.
- Migration names (`freedom_ls_content_engine.0017_alter_file_file`,
  `freedom_ls_organisations.0003_alter_organisation_logo`) are verbatim and correct; neither touches data.
- `build_storages()` signature, "emits all seven keys unconditionally," `reports_alias=` kwarg — all match
  `storage.py:140-163`.
- Step 4's advice to drop the (now nonexistent) `freedom_ls_reports.W001` silence entry is correct.
- Step 5's `AWS_S3_<PURPOSE>_<PROPERTY>` resolution order and the six purposes
  `PUBLIC, COURSE_MEDIA, USER_UPLOADS, GENERATED, CERTIFICATES, DEFAULT` are correct verbatim.
- Step 6's per-alias `QUERYSTRING_AUTH=false` vars for `public`/`certificates`, and "never use the shared
  form... two of which hold personal data," are correct.
- Step 8's claim that an undeclared-`storage=` field falls to `default`, "a bucket nothing should ever
  write to," matches `SKILL.md` and `env_example`.
- `settings_base.py`'s `public` entry is the only entry in the base `STORAGES` dict carrying an `OPTIONS`
  key — the document's framing that logo overwrite is special-cased is correct (only its "no `OPTIONS` key"
  blanket instruction two lines earlier is wrong — see defect #9).
