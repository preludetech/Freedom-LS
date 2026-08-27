# FLS Storage Surface — Full Codebase Inventory

Exhaustive grep/read-based inventory of everything that touches file storage in this repo, for the
`prod_bucket_setup` spec (splitting the single R2 bucket into `public` / `course-media` /
`learner-uploads` / `generated` aliases). All claims below carry `path:line`. Searched terms:
`FileField`, `ImageField`, `storage=`, `storages\[`, `STORAGES`, `MEDIA_ROOT`, `MEDIA_URL`,
`default_storage`, `.url`, `S3Storage`, `AWS_`, `upload_to`, `InvalidStorageError`, `SimpleUploadedFile`.

## 1. Every model field that stores a file

Repo-wide, there are exactly **three** `FileField`/`ImageField` declarations on live (non-migration,
non-factory) models. No others exist anywhere in `freedom_ls/`, `demo_content/`, `claude_plugins/`, or
any `qa_helpers`/test app.

| App | Model | Field | `upload_to` | `storage=` | `path:line` |
|---|---|---|---|---|---|
| `content_engine` | `File` | `file` | `file_upload_handler` (callable, `content_engine/{stem}{pk}{ext}`) | **none — falls to `storages["default"]` implicitly** | `freedom_ls/content_engine/models.py:590` (handler at `:570-577`) |
| `organisations` | `Organisation` | `logo` (`ImageField`) | `organisation_logo_upload_to` (callable, `organisations/{pk}{ext}`) | **none — falls to `storages["default"]` implicitly** | `freedom_ls/organisations/models.py:31-35` (handler at `:17-25`) |
| `reports` | `GeneratedReport` | `file` | `report_upload_path` (callable, `reports/{pk}-cohort-report.pdf`) | `get_reports_storage` — resolves `storages[REPORTS_STORAGE_ALIAS]`, falls back to `storages["default"]` on `InvalidStorageError` | `freedom_ls/reports/models.py:73-75` (handler `:24-33`, resolver `:36-41`) |

**Flag: two of the three fields (`content_engine.File.file`, `organisations.Organisation.logo`) have NO
explicit `storage=` argument and therefore silently use `storages["default"]`.** Only `reports` uses the
alias-resolution pattern the idea proposes extending to the other two.

Both `upload_to` callables key the path only on the instance pk plus extension — never the uploaded
filename — which is what prevents path traversal / overwrite collisions
(`freedom_ls/organisations/models.py:20-22` docstring makes this explicit; `report_upload_path`'s
docstring at `freedom_ls/reports/models.py:24-30` states the same reasoning for reports).

**Migrations** (for completeness, not separately actionable):
- `freedom_ls/content_engine/migrations/0001_initial.py:512` — original field, `upload_to="media/content_engine"` (string, not the current callable).
- `freedom_ls/content_engine/migrations/0002_alter_file_file.py:17` — alters to the current `file_upload_handler` callable.
- `freedom_ls/organisations/migrations/0001_initial.py:26` — matches current model exactly, including validators.
- `freedom_ls/reports/migrations/0001_initial.py:30` — matches current model exactly, including `storage=get_reports_storage`.

**Test factories that touch these fields** (not model fields themselves, listed since they show the
only other file-producing code paths):
- `freedom_ls/content_engine/factories.py:170` — `factory.django.FileField(filename="test.txt")` for `File.file`.
- `freedom_ls/reports/factories.py` exists (`GeneratedReportFactory`) but leaves `file` blank by default — tests explicitly call `report.file.save(...)` when they need bytes on disk (see §6).

No `FileField`/`ImageField` matches anywhere else — confirmed by the repo-wide grep for both terms
returning only the above three declarations (plus their migrations, factories, and the string literal in
`spec_dd/0. drafts/application-forms/idea.md:134`, which is an unimplemented draft, not code).

## 2. Every read path — how bytes reach a browser

| Field | Read path | Mechanism | Signed/direct vs. through-Django |
|---|---|---|---|
| `content_engine.File.file` | `{{ file_obj.file.url }}` in `freedom_ls/content_engine/templates/cotton/picture.html:35` and `:95` | `<img src=...>` | Signed URL, direct to storage |
| `content_engine.File.file` | `{{ file_obj.file.url }}` in `freedom_ls/content_engine/templates/cotton/pdf-embed.html:21` | `<iframe>`/embed `src` | Signed URL, direct to storage |
| `content_engine.File.file` | `{{ file_obj.file.url }}` in `freedom_ls/content_engine/templates/cotton/file-download.html:17` | `<a href=...>` | Signed URL, direct to storage |
| `content_engine.File.file` | `{{ file_obj.file.url }}` in `freedom_ls/content_engine/templates/cotton/card.html:32` | `<img src=...>` (a fourth template, not named in the idea) | Signed URL, direct to storage |
| `content_engine.File.file` | Django admin change form | `FileAdmin` exposes the raw `file` field in its fieldsets (`freedom_ls/content_engine/admin.py:262-278`, field listed at `:274`) | Admin's `ClearableFileInput` renders a `Currently: <a href="{{ value.url }}">` link — same signed-URL mechanism, but through the staff admin UI, not a content template |
| `organisations.Organisation.logo` | `{{ course_organisation.logo.url }}` in `freedom_ls/learner_interface/templates/learner_interface/partials/course_toc_header.html:28` (guarded by `{% if course_organisation.logo %}` at `:26`) | `<img src=...>` | Signed URL, direct to storage |
| `organisations.Organisation.logo` | Django admin change form | `OrganisationAdmin` lists `"logo"` in `fields` (`freedom_ls/organisations/admin.py:20`) | Same `ClearableFileInput` `.url` link pattern as above |
| `reports.GeneratedReport.file` | `download_report_view` (`freedom_ls/reports/views.py:109-125`) | `report.file.open("rb")` (`:120`) fed into `FileResponse(..., as_attachment=True, filename=...)` (`:123`), `Cache-Control: private, no-store, must-revalidate` set explicitly (`:124`) | **Streamed through Django**, never `.url` — reached only via the admin-namespaced view wired by `GeneratedReportAdmin.get_urls()` (per module docstring `freedom_ls/reports/views.py:1-6`), behind `can_view_cohort()` (`:114`) |
| `reports.GeneratedReport.file` | `GeneratedReportAdmin` changelist | Explicitly does **not** expose `.url` or a raw download link — asserted by test (`freedom_ls/reports/tests/test_admin.py:94-106`, e.g. `assert report.file.url not in response.content.decode()` at `:106`) | N/A — deliberately no direct-storage path |

**Server-side reads during rendering (a different access pattern — files read by the app process, not
served to a browser):**

- `freedom_ls/reports/render.py` resolves a **static** header logo, not `Organisation.logo`:
  `_resolve_logo(site_config.HEADER_LOGO_STATIC_PATH)` at `freedom_ls/reports/tests/test_render.py:181`
  (test-side evidence of the call signature); the render module itself reads fonts and the compiled
  Tailwind bundle through `django.contrib.staticfiles.finders.find(...)`
  (`freedom_ls/reports/checks.py:61`, `:100` show the same finder idiom used at render time) —
  **all static-file reads, never object storage.** No code path in `render.py` reads
  `Organisation.logo` or `content_engine.File.file`.
- `freedom_ls/accounts/email_utils.py:418-426` (`resolved_email_logo_path`) and `:589-600`
  (`email_logo_dimensions`) also resolve only `EMAIL_LOGO_STATIC_PATH` / `HEADER_LOGO_STATIC_PATH`
  via `finders.find` (`:600`) — again a static path, never a storage-backed field. **Confirms the idea's
  claim that `HEADER_LOGO_STATIC_PATH` and `Organisation.logo` are two unrelated logo concepts**: the
  former is WhiteNoise-served static, resolved by both `reports/render.py` and `accounts/email_utils.py`;
  the latter is the only one that touches object storage, and only `course_toc_header.html:28` reads it.

No email attachment sends any of the three fields' bytes — no matches for the field names inside
`freedom_ls/accounts/email_utils.py` or elsewhere combined with `attach`/`EmailMessage`.

No API serializer exists for any of the three fields — no DRF/serializer classes reference `file` or
`logo` anywhere in the repo (confirmed by the `.url` grep across `*.py`, §2 above, returning only
test assertions and the admin/view code already listed).

## 3. Every place a storage alias is resolved

- `freedom_ls/reports/models.py:36-41` — `get_reports_storage()`, the only alias-resolution helper in
  the codebase today: `storages[config.REPORTS_STORAGE_ALIAS]`, `except InvalidStorageError: return
  storages["default"]`. This is the pattern named in the idea as the template to copy for
  `content_engine.File` and `Organisation.logo`.
- `freedom_ls/reports/models.py:4` — imports `InvalidStorageError, Storage, storages` from
  `django.core.files.storage`. No other file in the repo imports `InvalidStorageError` or does a
  `storages[...]` lookup — confirmed by grep; `content_engine.File.file` and `Organisation.logo` have
  **no equivalent resolver at all**, they rely purely on Django's built-in default-storage fallback for
  a `FileField` with no `storage=` kwarg.
- `config/settings_prod.py:136-141` — the one place `STORAGES` itself is assembled (see §4).
- No other `get_..._storage()`-shaped helper exists anywhere in `freedom_ls/`.

## 4. Settings surface

Three settings modules, confirmed by glob (`config/settings_base.py`, `config/settings_dev.py`,
`config/settings_prod.py` — no others match `config/settings*.py`):

- `config/settings_base.py` — shared defaults, imported by both dev and prod via `from .settings_base
  import *`.
- `config/settings_dev.py` — extends base; declares **no `STORAGES` override at all** (confirmed:
  no `STORAGES` token anywhere in the file). `MEDIA_ROOT`/`MEDIA_URL` therefore come from
  `settings_base.py` and Django's implicit `storages["default"]` is `FileSystemStorage` rooted there.
- `config/settings_prod.py` — the only module that assembles `STORAGES` and the only R2/S3 wiring.

### `MEDIA_ROOT` / `MEDIA_URL`

- Declared once, in the base module: `MEDIA_URL = "media/"` and `MEDIA_ROOT = BASE_DIR / "media"`
  (`config/settings_base.py:257-258`). Neither is overridden in `settings_dev.py` or
  `settings_prod.py`. `MEDIA_ROOT` is only consumed when `storages["default"]` falls back to
  `FileSystemStorage` — i.e., dev/test always, and prod whenever `AWS_STORAGE_BUCKET_NAME` is unset
  (`config/settings_prod.py:130-133`).

### `config/settings_prod.py` — the R2/S3 assembly (lines 112-141)

```
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")          # :114
if AWS_STORAGE_BUCKET_NAME:                                              # :116
    default_storage = build_s3_media_storage(                           # :119
        bucket_name=AWS_STORAGE_BUCKET_NAME,
        access_key=os.getenv("AWS_S3_ACCESS_KEY_ID"),                    # :121
        secret_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),                # :122
        endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"),                   # :123
        region_name=os.getenv("AWS_S3_REGION_NAME"),                     # :124
        custom_domain=os.getenv("AWS_S3_CUSTOM_DOMAIN"),                 # :125 (unset => private signed URLs)
        querystring_auth=env_bool("AWS_QUERYSTRING_AUTH", True),         # :127 (default True = private)
        querystring_expire=env_int("AWS_QUERYSTRING_EXPIRE", 3600),      # :128
    )
else:
    default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}   # :131-133

STORAGES = {                                                              # :136
    "default": default_storage,                                          # :137
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},  # :138-140
}
```

**Env vars read, exact names, defaults:**

| Env var | Read at | Default when unset |
|---|---|---|
| `AWS_STORAGE_BUCKET_NAME` | `config/settings_prod.py:114` | `None` → falls to `FileSystemStorage` |
| `AWS_S3_ACCESS_KEY_ID` | `:121` | `None` |
| `AWS_S3_SECRET_ACCESS_KEY` | `:122` | `None` |
| `AWS_S3_ENDPOINT_URL` | `:123` | `None` |
| `AWS_S3_REGION_NAME` | `:124` | `None` → `build_s3_media_storage` defaults to `"auto"` (`freedom_ls/deployment/storage.py:27`) |
| `AWS_S3_CUSTOM_DOMAIN` | `:125` | `None` → private signed URLs (comment on the same line) |
| `AWS_QUERYSTRING_AUTH` | `:127` via `env_bool` | `True` (private) |
| `AWS_QUERYSTRING_EXPIRE` | `:128` via `env_int` | `3600` seconds |

**`STORAGES` today declares exactly two keys, `"default"` and `"staticfiles"`** — confirmed at
`config/settings_prod.py:136-141`. This is the literal basis of the idea's central defect claim: there
is no `"reports"` key, so `get_reports_storage()`'s `except InvalidStorageError` branch
(`freedom_ls/reports/models.py:40-41`) is always taken in this repo's own production settings.

### `freedom_ls/deployment/storage.py` (full file, 39 lines)

`build_s3_media_storage(*, bucket_name, access_key, secret_key, endpoint_url, region_name,
custom_domain, querystring_auth, querystring_expire) -> dict[str, object]` (`:6-38`). Returns
`{"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {...}}`. Notable behavior:
- `region_name or "auto"` (`:27`) — R2-specific default.
- `client_config=Config(request_checksum_calculation="when_required",
  response_checksum_validation="when_required")` (`:31-34`) — works around an R2-incompatible
  boto3 >=1.35.99 checksum header, per the docstring (`:19`).
- `custom_domain` is only added to `options` if truthy (`:36-37`) — omitting it is what keeps URLs
  signed/private.
- The docstring (`:17-20`) states this function is already **alias-agnostic** — it builds one
  `STORAGES[...]` entry's value, not tied to the `"default"` key by name. This is the function the idea
  says "should need no change" to be called once per alias.

### Static files / WhiteNoise

- `INSTALLED_APPS` includes `"whitenoise.runserver_nostatic"` (`config/settings_base.py:74`) and
  `django.contrib.staticfiles` (`:80`).
- `MIDDLEWARE` includes `"whitenoise.middleware.WhiteNoiseMiddleware"`
  (`config/settings_base.py:145`), positioned right after `SecurityMiddleware`.
- `STATIC_URL = "static/"`, `STATICFILES_DIRS = [BASE_DIR / "static"]`
  (`config/settings_base.py:243-244`).
- `STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")` is set **only** in
  `config/settings_prod.py:86` — dev/test have no `STATIC_ROOT` (WhiteNoise's `runserver_nostatic` /
  Django's dev static serving is used instead).
- `STORAGES["staticfiles"]` is hardcoded to
  `"whitenoise.storage.CompressedManifestStaticFilesStorage"` (`config/settings_prod.py:138-140`) with
  **no env var, no bucket, no conditional** — confirming the idea's claim that static files are never
  in a bucket. This is the only place `"staticfiles"` is assembled; no other file references an
  S3/R2 backend for static assets.

## 5. The app-settings and system-check patterns to copy

### `freedom_ls/base/app_settings.py` (full file, 76 lines) — precise shape

- `Setting(NamedTuple)` — `default: object = None`, `required: bool = False` (`:11-15`).
- `AppSettings.declared_settings: dict[str, Setting] = {}` (`:28`) — subclasses override this dict.
- `AppSettings.__getattr__` (`:30-47`): looks up the name in `declared_settings`, raises
  `AttributeError` if not declared (`:32-34`); reads `getattr(settings, name, None)`; strips strings;
  if the value is non-empty, returns it (`:38-39`); else, if `Setting.required`, raises
  `ImproperlyConfigured` lazily on read, never at import (`:40-44`); else returns
  `copy.deepcopy(setting.default)` (`:47`) — the deepcopy is deliberate, to stop a caller mutating a
  shared mutable default in place.
- `AppSettings.missing_required()` (`:49-59`) — never raises; returns the list of required-but-unset
  names, used by system checks.
- `required_settings_errors(config, app_label) -> list[CheckMessage]` (`:62-75`) — the single reusable
  `E001` body: one `Error(..., id=f"{app_label}.E001")` per name in `config.missing_required()`.

**How `reports` uses it, as the exact template to copy** (`freedom_ls/reports/config.py:69-101`):
`class ReportsConfig(AppSettings)` declares `REPORTS_STORAGE_ALIAS: str` with
`declared_settings = {"REPORTS_STORAGE_ALIAS": Setting(default="reports"), ...}` (`:78-79`), and a
module-level singleton `config = ReportsConfig()` (`:101`) that other modules import
(`from freedom_ls.reports.config import config`, used in `models.py:8` and `checks.py:32/42/77`).

**The exact `W001` check to copy** (`freedom_ls/reports/checks.py:37-55`):
```python
@register()
def check_reports_storage_alias_configured(**kwargs: object) -> list[CheckMessage]:
    """W001: Warn when REPORTS_STORAGE_ALIAS names no key in settings.STORAGES."""
    from django.conf import settings
    from freedom_ls.reports.config import config
    if config.REPORTS_STORAGE_ALIAS in settings.STORAGES:
        return []
    return [
        Warning(
            f"REPORTS_STORAGE_ALIAS={config.REPORTS_STORAGE_ALIAS!r} is not a key "
            f"in settings.STORAGES. Reports will fall back to the default "
            f"storage, which may be a publicly served MEDIA_ROOT.",
            hint="Declare a private storage alias in settings.STORAGES.",
            id="freedom_ls_reports.W001",
        )
    ]
```
Note the deferred imports of `settings` and `config` inside the function body (`:40-42`) — this is
deliberate so the check module itself has no import-time dependency on settings being configured.

**Retired-check-id convention** (`freedom_ls/reports/checks.py:14`, in the module docstring):
`"W003 — Retired. Do not reuse the id: a project may still be silencing it."` This is the only
retired-id example in the codebase (no other `checks.py` has a "Retired" entry) — it establishes the
convention that a spec adding new `*_STORAGE_ALIAS` warnings should follow: never renumber or reuse a
check id once shipped, mark retired ids explicitly in the docstring instead of deleting them.

### Every app with a `config.py`

`freedom_ls/accounts/config.py`, `freedom_ls/base/config.py`, `freedom_ls/content_engine/config.py`,
`freedom_ls/course_access/config.py`, `freedom_ls/deployment/config.py`, `freedom_ls/health/config.py`,
`freedom_ls/icons/config.py`, `freedom_ls/learner_management/config.py`,
`freedom_ls/markdown_rendering/config.py`, `freedom_ls/reports/config.py`,
`freedom_ls/role_based_permissions/config.py`, `freedom_ls/site_aware_models/config.py`,
`freedom_ls/webhooks/config.py` — **13 apps.**

### Every app with a `checks.py`

`freedom_ls/accounts/checks.py`, `freedom_ls/base/checks.py`, `freedom_ls/content_engine/checks.py`,
`freedom_ls/course_access/checks.py`, `freedom_ls/deployment/checks.py`, `freedom_ls/icons/checks.py`,
`freedom_ls/learner_interface/checks.py`, `freedom_ls/reports/checks.py` — **8 apps.**

### What this means for the two apps the idea targets

- **`organisations`** has **neither** a `config.py` nor a `checks.py` today. A
  `ORGANISATIONS_LOGO_STORAGE_ALIAS`-shaped setting (or similarly named) needs both files created from
  scratch, following the `reports` shape exactly (`AppSettings` subclass +
  `required_settings_errors` + a `W00x` alias-check).
- **`content_engine`** already has both `freedom_ls/content_engine/config.py` (13 lines,
  `ContentEngineConfig`, only `E001` for `ADMONITION_TYPES`) and `freedom_ls/content_engine/checks.py`
  (20 lines, only the `E001` check) — a `CONTENT_MEDIA_STORAGE_ALIAS`-shaped setting would extend the
  existing `declared_settings` dict and add one new `W00x` check function to the existing file, not
  create new machinery.
- Confirmed: `freedom_ls/content_engine/config.py:6-19` declares nothing storage-related today; no
  `STORAGE_ALIAS`-named setting exists outside `reports`.

## 6. Tests that touch storage

**Storage-specific fixtures / overrides:**

- `freedom_ls/conftest.py:31-41` — `_isolate_media_root` (autouse): redirects `settings.MEDIA_ROOT` to
  `tmp_path` for every test in the suite, with a docstring explaining that without it every test saving
  a file (e.g. an organisation logo) would write into the real working-tree `media/` directory
  (`:34-39`). This is the global safety net; it covers `content_engine.File` and `Organisation.logo`
  but **not** `reports`, since `reports` resolves through the `"reports"` alias, not `"default"`.
- `freedom_ls/reports/tests/conftest.py:15-31` — `isolated_reports_storage` (autouse, scoped to the
  `reports` app's own test tree): monkeypatches `settings.STORAGES` to add a `"reports"` key backed by
  `FileSystemStorage` rooted at `tmp_path`, with a docstring explaining that `settings_base` /
  `settings_dev` declare no `STORAGES` at all, so without this fixture `get_reports_storage()` would
  fall through to `MEDIA_ROOT` on every report-saving test (`:19-23`). This is the direct precedent for
  whatever per-alias test isolation the new `content-media`/`public` aliases will need.
- `freedom_ls/reports/tests/test_checks.py:23-51` — `TestReportsStorageAliasCheck`, two cases:
  `override_settings(STORAGES={...})` **without** a `"reports"` key asserts the `W001` fires
  (`:24-37`); **with** one, asserts silence (`:39-51`). This is the exact test shape a new alias check
  would replicate.
- `freedom_ls/reports/tests/test_deletion_hygiene.py` (76 lines, all 5 tests) — asserts
  `report.file.storage.exists(...)` goes `False` after `.delete()` at the model, queryset, and
  cascading-cohort-delete levels (`:16-53`), and that sibling reports' files survive a sibling's
  deletion (`:55-66`). Reads `storage = report.file.storage` directly (`:21`, `:33`, `:46`, `:61`) —
  i.e. it exercises whatever storage backend is configured via the fixture above, not a hardcoded
  backend.
- `freedom_ls/reports/tests/test_admin.py:94-106` — `test_changelist_html_contains_no_raw_storage_url`
  asserts `report.file.url not in response.content.decode()` (`:106`), the one place a test explicitly
  checks a `.url` value is **absent** from rendered output (this locks in the "never a `.url` path"
  guarantee for reports named in §2).

**`SimpleUploadedFile` / upload-flow tests:**

- `freedom_ls/organisations/tests/test_admin.py:8` imports `SimpleUploadedFile`, used at `:112` to
  exercise the logo upload through the admin form.
- No other `SimpleUploadedFile` usage found repo-wide (confirmed by grep of `freedom_ls/`).

**`.url` assertions outside the above:**

- `freedom_ls/learner_interface/tests/test_player_organisation.py:77` — `assert organisation.logo.url
  in chip` (positive assertion the logo URL renders in `course_toc_header.html`).
- `freedom_ls/organisations/tests/test_models.py:42` and `:49` — exercise
  `organisation_logo_upload_to(...)` directly, including a path-traversal payload
  (`"../../../etc/passwd.png"` at `:49`) to assert the pk-based path scheme neutralises it.

**Pytest marker taxonomy** (`pyproject.toml:80-85`): `playwright`, `ci_only`, `fls_internal`,
`weasyprint`. `addopts` at `pyproject.toml:79` runs with `-m 'not ci_only and not weasyprint'` by
default — i.e. `weasyprint`-marked (report-rendering) tests are opt-in locally, relevant because
report-rendering tests are the ones most likely to touch the `"reports"` storage alias end-to-end.
None of the four existing markers is storage-specific; a spec that wants a
`requires-real-object-storage`-shaped integration test would need a new marker.

No test overrides `MEDIA_URL` (only `MEDIA_ROOT`), and no test constructs an `S3Storage`/moto-style
mock — every storage-touching test in the repo uses `FileSystemStorage` under a `tmp_path`, confirmed
by the absence of any `boto3`/`moto`/`S3Storage` reference inside `freedom_ls/**/tests/`.

## 7. Documentation that must be updated

### `docs/deployment-security-checklist.md` — env-var table (§10, "AWS / S3 Storage")

Lines `184-192`:
```
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket name for media storage. |
| `AWS_S3_ACCESS_KEY_ID` | AWS access key ID. |
| `AWS_S3_SECRET_ACCESS_KEY` | AWS secret access key. |
| `AWS_S3_ENDPOINT_URL` | Custom S3 endpoint URL (for S3-compatible services). |
| `AWS_S3_REGION_NAME` | Region for the S3-compatible bucket (default `auto` for R2). |
```
**Already incomplete today, independent of this idea**: it omits `AWS_S3_CUSTOM_DOMAIN`,
`AWS_QUERYSTRING_AUTH`, and `AWS_QUERYSTRING_EXPIRE`, all three of which
`config/settings_prod.py:125-128` reads. It also has no row for `REPORTS_STORAGE_ALIAS`
(`freedom_ls/reports/config.py:79`) even though that is a production-relevant env var today. A
four-bucket layout would need this entire table restructured (one bucket name / credential set per
alias) rather than patched.

### `docs/product/security-and-data-handling.md`

- **Line 12**: "**Built:** Media in object storage is private by default, served via time-limited
  signed links rather than permanently public URLs." — Still accurate for `content_engine.File` and
  `Organisation.logo` (both fall to `storages["default"]`, which defaults `querystring_auth=True`,
  `config/settings_prod.py:127`), but says nothing about reports sharing that same bucket, which is
  the idea's core complaint.
- **Line 14**: "**Operational:** Report PDFs are written to a private storage location once an
  operator configures one. Left unconfigured they fall back to default media storage — which may be
  publicly served — and a startup check warns about it." — Technically hedged correctly ("once an
  operator configures one" / "may be"), but read together with line 140 below, a reviewer would not
  learn that **this repo's own production settings never configure `REPORTS_STORAGE_ALIAS`** — the
  "unconfigured" branch is FLS's actual current state, not a hypothetical.
- **Line 140** (`### Generated Cohort Reports` → `**Storage (operational).**`): "Report files are
  written to a storage location configured separately from ordinary media, through the
  `REPORTS_STORAGE_ALIAS` setting. A deployment that has not configured one falls back to default
  media storage — which may be publicly served — and the application raises a startup warning naming
  the gap, so it surfaces at deploy time rather than after a leak." — **This is the line the idea
  names as inaccurate** (`spec_dd/2. in progress/prod_bucket_setup/idea.md:26-27`). The sentence
  describes the mechanism correctly in the abstract, but reads as reassurance ("configured
  separately... the application raises a startup warning... surfaces at deploy time") without
  disclosing that in FLS's own shipped `config/settings_prod.py` the warning **is currently firing**
  (`freedom_ls_reports.W001`, `freedom_ls/reports/checks.py:39`) because `STORAGES` there
  (`config/settings_prod.py:136-141`) never declares a `"reports"` key. A reader of this doc alone
  would not know FLS's own reference deployment is presently non-compliant with its own documented
  guidance.
- **Line 78-84** (`### Media File Access Control`) — accurate as written; no bucket-count claim, so
  unaffected by a four-bucket split as long as the private/signed-URL behaviour is preserved per
  alias.

### `docs/product/deployment.md`

- **Line 56**: "**Object storage for media** — media is served from S3-compatible object storage
  (Cloudflare R2), enabled by setting the storage bucket environment variable; without it, media falls
  back to local filesystem storage. Media is **private by default**, with time-limited signed links
  rather than permanently public URLs." — Singular "the storage bucket environment variable" (i.e.
  `AWS_STORAGE_BUCKET_NAME`) becomes false the moment there is more than one bucket/alias — this
  sentence needs to become plural and per-alias.
- **Line 57**: "**Cohort progress reports** — ... reports hold real learner names and quiz answers, so
  they are written to a private storage location configured separately from ordinary media, and a
  deployment that has not configured one gets a startup warning rather than a silent fallback to
  publicly served storage." — Same defect as security-and-data-handling.md:140: correct in the
  abstract, silent about FLS's own prod settings not doing this today.

### `docs/product/roadmap.md`

- **Line 9**: lists "per-request access-controlled media downloads" and "data-retention/data-subject-
  rights tooling" as not-built — both relevant constraints the spec should reference, not contradict.
- **Line 53**: "**Authored application form** — applying collects no questions, answers, or file
  uploads. A multi-step form with configurable questions and file upload is deferred to a follow-up." —
  matches the idea's `learner-uploads` bucket rationale exactly (§8 below).
- **Line 98**: "per-request access-controlled media downloads" — the roadmap item the idea explicitly
  scopes out (`spec_dd/2. in progress/prod_bucket_setup/idea.md:218-221`).
- **Line 143**: "Completing a course produces a finish page but no certificate or downloadable
  completion evidence." — matches certificates (§8 below).
- No line in `roadmap.md` currently claims anything about bucket count or storage aliases, so nothing
  there is factually contradicted by a four-bucket split; it simply doesn't yet reflect this idea.

### `claude_plugins/fls-dev/resources/template_repo_manifest.md`

- **Lines 205-206** (checklist for a downstream project's `settings_prod.py`): "S3 media storage block
  (conditional on `AWS_STORAGE_BUCKET_NAME`)" and "`STORAGES` dict: whitenoise for staticfiles, S3 or
  filesystem for default." This is the checklist a downstream concrete project's own settings are
  audited against — a four-alias layout means this checklist needs to grow from "one conditional S3
  block" to "N per-alias blocks," and any spec here should update it or the checklist will keep
  auditing downstream projects against the single-bucket shape.

### `upgrade_notes.md` files

- `spec_dd/3. done/2026-08-21_20:12_basic_reports/upgrade_notes.md:14` and `:208-213` — the existing
  precedent for how a storage-alias-introducing spec writes its downstream migration instructions
  (told downstream projects to add a `"reports"` key to `STORAGES` or accept the fallback warning).
  This is the shape a new `prod_bucket_setup` upgrade note should follow, multiplied by three new
  aliases.
- No other `upgrade_notes.md` in `spec_dd/3. done/` or `spec_dd/2. in progress/` mentions `STORAGES`
  or bucket layout, confirmed by the earlier repo-wide `STORAGES` grep.

## 8. Future file-owning features already on the books

| Feature | Where described | Bucket-layout implication |
|---|---|---|
| Certificates | `spec_dd/1. next/certificates/idea.md:1-3` — "Implement certificates... verifiable, tamper-evident certificates with a public verify URL." Also `docs/product/roadmap.md:139-143` ("Completion Certificates" section; no certificate or downloadable completion evidence exists yet), and `docs/product/roadmap.md:38` ("no organisation branding in emails or certificates"). | **Open question, not settled**: the idea file itself flags this (`spec_dd/2. in progress/prod_bucket_setup/idea.md:163-164, 205-208`) — if "verify URL" serves the PDF itself rather than a rendered attestation page, certificates belong in `fls-prod-public`, not `fls-prod-generated`, contradicting the idea's default placement of certificates alongside reports. The 3-line idea doc gives no detail on what "verify" renders, so this cannot be resolved from `certificates/idea.md` alone — it is a genuine open design question the spec must close before certificates are built, not something this research can settle by reading more code (no certificate code exists yet). |
| User data retention / erasure | `spec_dd/1. next/user-data-retention-idea.md` (full file, 38 lines) | **Assumes nothing about bucket boundaries.** The file is entirely about DB-row retention/anonymisation policy per model (`:9-21`) and does not mention file storage, buckets, or `FileField`s anywhere — confirmed by reading the full file. The idea's claim that this future work "wants to drive... or inherit" bucket boundaries (`spec_dd/2. in progress/prod_bucket_setup/idea.md:209-210`) is therefore an open question this file does not answer either way; it is silent on storage entirely, which the spec should note rather than assume alignment. |
| Application-form file attachments | `docs/product/roadmap.md:53` (see quote above); fuller design in `spec_dd/0. drafts/application-forms/idea.md:113-149` (a draft, not in `1. next/`) | The draft already specs the exact shape the idea's `learner-uploads` bucket wants: `ApplicationFile.file` as `FileField(storage=<private>, upload_to=<non-guessable, pk-based>)` (`:134`), with `scan_status` as a "seam; no scanner here" field (`:138`) and `superseded` for audit-preserving replace-history (`:139`). This draft is strong independent evidence for the `learner-uploads` bucket's versioning/erasure-boundary rationale in the idea (`idea.md:130-134`). |
| Learner documents / profile pictures | Named only in the idea itself (`spec_dd/2. in progress/prod_bucket_setup/idea.md:85, 125, 197`) — **no separate spec_dd idea file or roadmap line describes these yet.** No matches for "profile picture" anywhere under `spec_dd/1. next/` or `docs/product/roadmap.md`. | Purely a placeholder in this idea; nothing upstream to reconcile against. |

## 9. Anything surprising

- **A fourth template reads `content_engine.File.file.url`** that the idea's own summary table omits:
  `freedom_ls/content_engine/templates/cotton/card.html:32` (`<img src="{{ file_obj.file.url }}"`), in
  addition to the three the idea names (`picture.html`, `pdf-embed.html`, `file-download.html`). Same
  access pattern (signed URL, direct to storage), so it doesn't change the bucket-layout conclusion,
  but the spec's read-path inventory should list four templates, not three.
- **Both admin change forms are an unlisted `.url` read path.** `FileAdmin`
  (`freedom_ls/content_engine/admin.py:262-278`) and `OrganisationAdmin`
  (`freedom_ls/organisations/admin.py:20`) both expose the raw file field, so Django's
  `ClearableFileInput` renders a `Currently: <a href="{{ value.url }}">` link in the staff admin for
  both `content_engine.File` and `Organisation.logo`. This is a signed-URL read path the idea's table
  doesn't mention at all (it only lists the public-facing templates and the reports admin, and
  explicitly proves reports do *not* leak `.url` in admin — but doesn't check whether the other two
  fields' admin forms do). Worth the spec confirming this is acceptable (staff-only surface) rather
  than assuming admin never touches storage URLs.
- **`GeneratedReport.__str__` names the organisation and cohort**
  (`freedom_ls/reports/models.py:87-95`) — not a storage concern per se, but relevant to the
  `fls-prod-generated` bucket's "narrowest credentials" framing: the delete-confirmation screen (which
  the docstring at `:88-91` says is the reason for this `__str__`) is itself a PII-adjacent admin
  surface worth being aware of when reasoning about "who can see what" for the generated bucket.
- **`freedom_ls/content_engine/management/commands/content_save.py:484`** has a comment mentioning
  "Save new file to proper upload_to location" but the command does not construct or resolve a storage
  alias itself — it's a plain comment, not a second resolver. Confirmed no `storages[...]` or
  `get_..._storage` call in that file.
- **The env-var table gap in `docs/deployment-security-checklist.md` (§7 above, lines 184-192)
  predates this idea** — `AWS_S3_CUSTOM_DOMAIN`, `AWS_QUERYSTRING_AUTH`, and `AWS_QUERYSTRING_EXPIRE`
  are all read by `config/settings_prod.py:125-128` today but were never added to the checklist table.
  This is a pre-existing documentation gap the spec will restructure anyway (moving from one bucket's
  vars to N buckets' vars), but worth flagging as a defect independent of the four-bucket decision.
- **No `InvalidStorageError` handling exists for `content_engine.File` or `Organisation.logo`
  at all** — since neither field passes `storage=`, there is no alias to mis-resolve; they always use
  whatever `storages["default"]` is. This means today there is structurally no way for these two
  fields to "fall back" the way reports does — the failure mode a new `*_STORAGE_ALIAS` setting would
  introduce for them (an alias that mis-resolves) does not exist yet, and the spec is adding a new
  fallback behavior, not fixing an existing broken one, for these two fields specifically.
- **`reports/tests/test_deletion_hygiene.py:65`** asserts `storage.exists("reports") is True` after a
  sibling report's file is deleted — i.e., the shared `reports/` prefix directory itself is expected to
  persist. Relevant if the spec changes the report `upload_to` prefix as part of aligning it with a new
  bucket/alias naming scheme — this test's exact string would need updating.

status: ok
