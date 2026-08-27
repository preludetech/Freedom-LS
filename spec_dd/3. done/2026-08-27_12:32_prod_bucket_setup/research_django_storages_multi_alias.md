# Research: `django-storages` multi-alias `STORAGES` for FLS

Scope: mechanics of Django's `STORAGES`/`storages` registry and `FileField(storage=...)`,
and idiomatic patterns for adding four storage aliases (public / course-media /
learner-uploads / generated) on top of the existing single-alias R2 setup, without
forcing downstream single-bucket or filesystem-only installs to change.

Sources consulted: the installed package source under
`.venv/lib/python3.13/site-packages/django/...` and
`.venv/lib/python3.13/site-packages/storages/...` (django-storages `>=1.14.6`,
pinned in `pyproject.toml:22`), the Django docs, the django-storages docs, and the
existing FLS repo files:
- `freedom_ls/deployment/storage.py`
- `config/settings_prod.py`
- `freedom_ls/reports/models.py`, `freedom_ls/reports/checks.py`, `freedom_ls/reports/config.py`
- `freedom_ls/content_engine/models.py` (`File.file`)
- `freedom_ls/organisations/models.py` (`Organisation.logo`)
- `freedom_ls/base/app_settings.py`, `freedom_ls/base/env.py`
- `freedom_ls/deployment/settings_defaults.py`, `freedom_ls/deployment/checks.py`

---

## 1. `FileField(storage=...)` and migrations

**One-line answer:** Passing a *callable* keeps the migration's `storage=` kwarg pointed
at the stable dotted import path of the callable, never at the resolved bucket/options —
that is exactly the mechanism the reports app already relies on. Passing a plain
`Storage` **instance** bakes that instance (and everything the migration serializer can
extract from it) into the migration file. A migration *is* generated whenever `storage`
changes from unset (implicitly `default_storage`) to anything else, callable or not.

**Detail**, from `django/db/models/fields/files.py` (`FileField.__init__` and
`.deconstruct()`, `.venv/lib/python3.13/site-packages/django/db/models/fields/files.py:246-312`):

```python
def __init__(self, verbose_name=None, name=None, upload_to="", storage=None, **kwargs):
    ...
    self.storage = storage if storage is not None else default_storage
    if callable(self.storage):
        # Hold a reference to the callable for deconstruct().
        self._storage_callable = self.storage
        self.storage = self.storage()          # called once, at field-definition time
        if not isinstance(self.storage, Storage):
            raise TypeError(...)
    ...

def deconstruct(self):
    name, path, args, kwargs = super().deconstruct()
    if kwargs.get("max_length") == 100:
        del kwargs["max_length"]
    kwargs["upload_to"] = self.upload_to
    storage = getattr(self, "_storage_callable", self.storage)
    if storage is not default_storage:
        kwargs["storage"] = storage
    return name, path, args, kwargs
```

Key facts:

- If `storage` is a **callable**, `deconstruct()` puts `_storage_callable` — the
  original callable object, e.g. `freedom_ls.reports.models.get_reports_storage` — into
  the migration's kwargs, *not* the `Storage` instance it returned. Django's migration
  writer serializes a plain function/callable by its dotted import path (see
  `django.db.migrations.serializer.FunctionTypeSerializer` /
  `TypeSerializer`), so the migration file literally contains
  `storage=freedom_ls.reports.models.get_reports_storage` — confirmed in the repo at
  `freedom_ls/reports/migrations/0001_initial.py:30`:
  ```python
  ('file', models.FileField(blank=True, storage=freedom_ls.reports.models.get_reports_storage, upload_to=freedom_ls.reports.models.report_upload_path)),
  ```
  No bucket name, credential, or `OPTIONS` value ever reaches the migration file this
  way. The callable is re-invoked (and re-resolves `storages[alias]`) every time the
  field is instantiated — at request time in the running app, and again when Django
  loads historical migration state for `makemigrations`/tests — so the migration stays
  correct even if the alias's backend/bucket changes later, and swapping buckets
  requires **no new migration** at all.
- If a **plain `Storage()` instance** is passed instead, `self.storage` is that instance
  directly; `_storage_callable` is never set, so `deconstruct()` puts the instance itself
  in `kwargs["storage"]`. Django's migration writer then needs the instance to be
  serializable — `S3Storage` (and `BaseStorage`) is decorated `@deconstructible`
  (`.venv/lib/python3.13/site-packages/storages/backends/s3.py:299-300`), which makes
  `MigrationWriter` re-emit the constructor call with its `**settings` kwargs, e.g.
  `storages.backends.s3.S3Storage(bucket_name='fls-prod-course-media', access_key=..., ...)`.
  That is precisely the outcome the spec must avoid: the bucket name (and, depending on
  how the instance was built, possibly credentials passed positionally/as kwargs) get
  frozen into migration history and diffed on every `makemigrations` run whenever the
  instance's constructor kwargs change.
- **A migration is generated on the unset → callable transition.** `FileField.storage`
  defaults to `django.core.files.storage.default_storage` (the `DefaultStorage`
  `LazyObject` singleton) when omitted. `deconstruct()` only omits `storage` from
  kwargs when `storage is not default_storage` is `False`, i.e. only when the field's
  storage *is* that exact singleton object. Any callable (even one that itself
  ultimately returns `storages["default"]`, e.g. `get_reports_storage` when
  `REPORTS_STORAGE_ALIAS` doesn't resolve) is a *different* object from
  `default_storage`, so the `storage=` kwarg is always emitted once a callable is
  attached — `makemigrations` will generate an `AlterField` migration the first time
  `content_engine.File.file` / `organisations.Organisation.logo` gain a
  `storage=get_<alias>_storage` argument. That generated migration only ever references
  the callable's dotted path (stable across environments/buckets), so it is safe to
  commit; it is not optional to avoid — Django will always detect the field change.

**Implication for the spec:** every per-field storage assignment must go through a
named, module-level callable (mirroring `get_reports_storage`), never a bare `Storage(...)`
instance and never a `lambda` (lambdas cannot be resolved to a dotted path by the
migration serializer and will raise `ValueError: Cannot serialize function: lambda` at
`makemigrations` time — see the "Migration Serializing" note in Django's model field
reference).

Docs: https://docs.djangoproject.com/en/5.2/ref/models/fields/#django.db.models.FileField.storage ,
https://docs.djangoproject.com/en/5.2/topics/migrations/#migration-serializing

---

## 2. The `storages` registry (`StorageHandler`)

**One-line answer:** `storages[alias]` is resolved lazily on first access per alias, the
resulting `Storage` instance is cached for the lifetime of the process, and
`InvalidStorageError` (a subclass of `ImproperlyConfigured`) is raised for an alias with
no key in `settings.STORAGES` or an unimportable `BACKEND`; the gotcha is that resolving
an alias too early (e.g. at import time / app-loading time, before `settings.STORAGES` is
fully assembled) can silently pin a stale or wrong snapshot for the whole process.

**Detail**, from `django/core/files/storage/handler.py` and `.../storage/__init__.py`:

```python
class StorageHandler:
    def __init__(self, backends=None):
        self._backends = backends
        self._storages = {}

    @cached_property
    def backends(self):
        if self._backends is None:
            self._backends = settings.STORAGES.copy()   # snapshot taken on FIRST access
        return self._backends

    def __getitem__(self, alias):
        try:
            return self._storages[alias]                 # cache hit
        except KeyError:
            try:
                params = self.backends[alias]
            except KeyError:
                raise InvalidStorageError(
                    f"Could not find config for '{alias}' in settings.STORAGES."
                )
            storage = self.create_storage(params)          # instantiates the backend
            self._storages[alias] = storage                # cached from here on
            return storage

    def create_storage(self, params):
        params = params.copy()
        backend = params.pop("BACKEND")
        options = params.pop("OPTIONS", {})
        try:
            storage_cls = import_string(backend)
        except ImportError as e:
            raise InvalidStorageError(f"Could not find backend {backend!r}: {e}") from e
        return storage_cls(**options)
```

```python
storages = StorageHandler()          # module-level singleton, django/core/files/storage/__init__.py:26
default_storage = DefaultStorage()   # LazyObject wrapping storages[DEFAULT_STORAGE_ALIAS]
```

- `storages.backends` is a `cached_property`: `settings.STORAGES` is copied into
  `self._backends` the **first time any alias is looked up**, then never re-read (in
  production; test's `override_settings` explicitly busts this — see below). If code
  mutates `settings.STORAGES` after that first access (e.g. a project appends an alias
  in a post-`ready()` hook), the append is invisible to `storages` for the rest of the
  process.
- Each `storages[alias]` call after the first for that alias returns the **same cached
  instance** (`self._storages[alias]`) — `S3Storage.__init__` (which opens no network
  connection itself, but does build a `botocore.config.Config`, parses `cloudfront_key`,
  etc.) runs exactly once per alias per process.
- `InvalidStorageError(ImproperlyConfigured)` is raised in two situations: (a) the alias
  key is absent from `settings.STORAGES` entirely, or (b) the alias exists but its
  `BACKEND` string doesn't import. This is exactly the exception `get_reports_storage()`
  catches (`freedom_ls/reports/models.py:38-41`).
- **Import-time vs call-time gotcha:** `storages[alias]` must not be evaluated at
  **module import time** (e.g. as a class-level default, `file = models.FileField(storage=storages["reports"])`
  evaluated while `models.py` is imported) because Django's app registry / settings may
  not be fully populated yet during that phase (app loading order, `AppConfig.ready()`
  not yet run, `override_settings` in tests not yet applied), and because it would defeat
  the whole point of `deconstruct()` treating a callable specially (see §1) — a directly
  evaluated instance gets baked into the field, not a callable reference. This is exactly
  why `get_reports_storage` is a **function** passed as `storage=get_reports_storage`
  (never called at class-body time) rather than `storage=storages["reports"]` or
  `storage=get_reports_storage()`: the call only happens (a) at `FileField.__init__`
  time when Django instantiates the field object during migration-state building /
  app loading, and (b) again whenever a migration operation deconstructs the field —
  both of which happen after settings and the app registry are ready.
- For tests: `django.test.signals.storages_changed` (`.venv/lib/python3.13/site-packages/django/test/signals.py:114-129`)
  resets `storages._backends = None` and `storages._storages = {}` whenever
  `override_settings(STORAGES=...)` fires, so `storages[alias]` re-resolves cleanly
  inside `@override_settings`/`SimpleTestCase.settings()` blocks. Outside test signal
  handling there is no automatic invalidation — this only matters for tests, not prod.

Docs: https://docs.djangoproject.com/en/5.2/ref/files/storage/#the-storages-object ,
https://docs.djangoproject.com/en/5.2/ref/settings/#storages

Repo file: `.venv/lib/python3.13/site-packages/django/core/files/storage/handler.py`,
`.venv/lib/python3.13/site-packages/django/core/files/storage/__init__.py`

---

## 3. The fallback-plus-warning pattern (`get_reports_storage`)

**One-line answer:** the existing shape (`try: storages[alias] except InvalidStorageError: storages["default"]`
plus a separate `W001` check) is a reasonable *starting point* for a single alias where
"default" is at least a plausible fallback, but for aliases whose entire purpose is to be
**more private/less public than default** (learner-uploads, generated reports), a silent
fallback to `default` is the wrong default behavior — it converts a config mistake into a
silent data-exposure bug, which is the exact motivating incident for this spec. At minimum
the check severity for privacy-sensitive aliases should be escalated, and at least one of
the two alternative shapes below should replace pure silent fallback for those aliases.

**Detail on the current shape** (`freedom_ls/reports/models.py:36-41`,
`freedom_ls/reports/checks.py:37-55`):

```python
def get_reports_storage() -> Storage:
    """The alias named by REPORTS_STORAGE_ALIAS, falling back to the default storage."""
    try:
        return storages[config.REPORTS_STORAGE_ALIAS]
    except InvalidStorageError:
        return storages["default"]
```
paired with a `Warning` (`freedom_ls_reports.W001`) whenever
`REPORTS_STORAGE_ALIAS not in settings.STORAGES`.

Tradeoffs of this exact shape:
- **Pro:** the app never hard-crashes at request time just because a downstream project
  didn't bother declaring a `"reports"` alias — reports still get written somewhere, and
  `manage.py check` (run in CI/on deploy in most Django setups) surfaces the misconfiguration
  as a `Warning`, not silently.
- **Con:** a `Warning` (not `Error`) does not fail `manage.py check` by default, does not
  fail `migrate`/`runserver` startup, and is trivially silenced via
  `SILENCED_SYSTEM_CHECKS`. A team that silences it once (e.g. during initial bring-up,
  intending to fix later) gets no further signal, ever, that report PDFs (or in the
  four-alias world: raw learner uploads) are landing in a bucket that is also serving
  public course media with public, unsigned URLs. The check only detects "alias is
  entirely undeclared" — it does **not** detect "alias is declared but points at the same
  bucket/backend as `default`", which is the more insidious and more likely misconfiguration
  (see §6).

**At least two alternative shapes**, in increasing strictness:

**(a) Always-declared alias, defaulted at the settings layer (no runtime fallback needed).**
Instead of the *model layer* catching `InvalidStorageError`, make it a **settings-layer**
contract: `STORAGES` always contains all four keys (public/course-media/learner-uploads/generated),
because the settings module itself points unconfigured aliases at whatever `default`
resolved to (see §4's `build_storages()` sketch). The model-layer helper then becomes:

```python
def get_learner_uploads_storage() -> Storage:
    """The alias named by LEARNER_UPLOADS_STORAGE_ALIAS.

    Always resolves: the settings layer guarantees every declared alias is a key in
    STORAGES, defaulting unconfigured ones to the same backend as "default" rather than
    omitting them. There is deliberately no except-and-fall-back-to-default here — see
    the module docstring and freedom_ls_learner_uploads.W001/E001.
    """
    return storages[config.LEARNER_UPLOADS_STORAGE_ALIAS]
```
This removes the silent app-layer fallback entirely and pushes the "did you configure a
distinct bucket" question to a system check that can compare *resolved* buckets (see §6),
not just alias presence. If `LEARNER_UPLOADS_STORAGE_ALIAS` is renamed by a project to
something that truly isn't in `STORAGES`, this now raises `InvalidStorageError` (a subclass
of `ImproperlyConfigured`) at first file access instead of silently degrading — a loud,
fail-fast failure mode consistent with the rest of FLS's config primitives
(`freedom_ls/base/env.py`'s `ImproperlyConfigured` raises, `freedom_ls/deployment/settings_defaults.py`'s
`require_secret_key()`).

**(b) Keep the try/except fallback, but make the *check* an Error for privacy-sensitive
aliases and add a "resolves to same backend as default" check.** If backward-compatible
graceful degradation at the model layer is still wanted (e.g. so a half-upgraded project
doesn't 500 on first request), keep `get_reports_storage()`'s shape, but:
  - split the check into an `Error` (`E00x`) for aliases whose OPTIONS imply "must be
    private" (querystring_auth=True intended) falling back to a `default` that is public,
    and a `Warning` for the less dangerous direction; or
  - raise instead of falling back when running with `DEBUG=False` (i.e. treat the
    fallback as a dev-only convenience), something like:
    ```python
    def get_learner_uploads_storage() -> Storage:
        try:
            return storages[config.LEARNER_UPLOADS_STORAGE_ALIAS]
        except InvalidStorageError:
            if not settings.DEBUG:
                raise
            return storages["default"]
    ```
    This keeps local dev/test frictionless (no bucket needed) while making a production
    deployment that never configured the alias crash loudly instead of quietly writing
    learner PII into a public bucket.

Recommendation for the spec to weigh: shape (a) — always-declared aliases via a settings
helper — is the cleanest because it moves the "what happens when unconfigured" decision
to one place (`build_storages()`), is trivially testable, and lets every per-app
`get_<alias>_storage()` function be a one-liner with no exception handling, while the
system check (§6) does the real work of catching the dangerous case (alias silently
sharing a bucket with `default`).

---

## 4. Graceful degradation for downstream projects

**One-line answer:** add a settings-layer helper, `build_storages()`, that always emits
all N aliases into `STORAGES`, resolving each alias's bucket config from a per-alias env
var with fallback to the existing shared `AWS_STORAGE_BUCKET_NAME`/credentials, and
falling back further to `FileSystemStorage` for every alias when no bucket at all is
configured — so a project that sets only the current five env vars gets exactly today's
behavior (one bucket, or filesystem), and a project that sets the new per-alias vars gets
genuinely separate buckets.

**Sketch**, extending `freedom_ls/deployment/storage.py` (`build_s3_media_storage` stays
as-is and becomes the single-alias building block):

```python
# freedom_ls/deployment/storage.py
from __future__ import annotations

import os
from dataclasses import dataclass

from botocore.config import Config

from freedom_ls.base.env import env_bool, env_int

# The alias names FLS apps import and reference in FileField(storage=...) callables.
ALIAS_PUBLIC = "public"
ALIAS_COURSE_MEDIA = "course-media"
ALIAS_LEARNER_UPLOADS = "learner-uploads"
ALIAS_GENERATED = "generated"

ALL_ALIASES = (ALIAS_PUBLIC, ALIAS_COURSE_MEDIA, ALIAS_LEARNER_UPLOADS, ALIAS_GENERATED)


def build_s3_media_storage(
    *,
    bucket_name: str,
    access_key: str | None,
    secret_key: str | None,
    endpoint_url: str | None,
    region_name: str | None,
    custom_domain: str | None,
    querystring_auth: bool,
    querystring_expire: int,
) -> dict[str, object]:
    """Unchanged — assembles one STORAGES entry for one R2 bucket."""
    ...  # exactly as today


@dataclass(frozen=True)
class _AliasEnv:
    """Per-alias env var name overrides, all falling back to the shared AWS_* names."""

    bucket_var: str
    access_key_var: str
    secret_key_var: str
    endpoint_var: str
    region_var: str
    custom_domain_var: str
    querystring_auth_var: str
    querystring_expire_var: str


def _alias_env(alias_env_prefix: str) -> _AliasEnv:
    return _AliasEnv(
        bucket_var=f"{alias_env_prefix}_BUCKET_NAME",
        access_key_var=f"{alias_env_prefix}_ACCESS_KEY_ID",
        secret_key_var=f"{alias_env_prefix}_SECRET_ACCESS_KEY",
        endpoint_var=f"{alias_env_prefix}_ENDPOINT_URL",
        region_var=f"{alias_env_prefix}_REGION_NAME",
        custom_domain_var=f"{alias_env_prefix}_CUSTOM_DOMAIN",
        querystring_auth_var=f"{alias_env_prefix}_QUERYSTRING_AUTH",
        querystring_expire_var=f"{alias_env_prefix}_QUERYSTRING_EXPIRE",
    )


def _alias_storage_entry(alias_env_prefix: str) -> dict[str, object] | None:
    """One STORAGES entry for one alias, or None if neither the per-alias nor the
    shared AWS_STORAGE_BUCKET_NAME env var names a bucket."""
    env = _alias_env(alias_env_prefix)
    bucket_name = os.getenv(env.bucket_var) or os.getenv("AWS_STORAGE_BUCKET_NAME")
    if not bucket_name:
        return None
    return build_s3_media_storage(
        bucket_name=bucket_name,
        access_key=os.getenv(env.access_key_var) or os.getenv("AWS_S3_ACCESS_KEY_ID"),
        secret_key=os.getenv(env.secret_key_var) or os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
        endpoint_url=os.getenv(env.endpoint_var) or os.getenv("AWS_S3_ENDPOINT_URL"),
        region_name=os.getenv(env.region_var) or os.getenv("AWS_S3_REGION_NAME"),
        custom_domain=os.getenv(env.custom_domain_var) or os.getenv("AWS_S3_CUSTOM_DOMAIN"),
        querystring_auth=env_bool(
            env.querystring_auth_var, env_bool("AWS_QUERYSTRING_AUTH", True)
        ),
        querystring_expire=env_int(
            env.querystring_expire_var, env_int("AWS_QUERYSTRING_EXPIRE", 3600)
        ),
    )


def build_storages(*, staticfiles: dict[str, object]) -> dict[str, dict[str, object]]:
    """Assemble the full STORAGES dict: "default" plus every FLS alias.

    Single-bucket compatibility: a project that sets only AWS_STORAGE_BUCKET_NAME (and
    the other un-prefixed AWS_* vars) gets that one bucket under every alias, because
    _alias_storage_entry() falls back to the shared env vars whenever a per-alias
    override is absent. Filesystem-only compatibility: a project that sets no bucket at
    all (AWS_STORAGE_BUCKET_NAME unset AND no per-alias var set) gets FileSystemStorage
    under every alias, unchanged from today.
    """
    default_entry = _alias_storage_entry("AWS_S3") or {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }

    storages: dict[str, dict[str, object]] = {"default": default_entry, "staticfiles": staticfiles}
    alias_prefixes = {
        ALIAS_PUBLIC: "AWS_S3_PUBLIC",
        ALIAS_COURSE_MEDIA: "AWS_S3_COURSE_MEDIA",
        ALIAS_LEARNER_UPLOADS: "AWS_S3_LEARNER_UPLOADS",
        ALIAS_GENERATED: "AWS_S3_GENERATED",
    }
    for alias, prefix in alias_prefixes.items():
        storages[alias] = _alias_storage_entry(prefix) or default_entry
    return storages
```

and `config/settings_prod.py` collapses to:

```python
from freedom_ls.deployment.storage import build_storages

STORAGES = build_storages(
    staticfiles={"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}
)
```

Notes on the sketch:
- `_alias_storage_entry(alias_prefix) or default_entry` is what gives graceful
  degradation: any alias whose per-alias env vars are entirely unset falls back to
  reusing the **exact same dict** the `default` alias uses. Because `StorageHandler.create_storage`
  (§2) instantiates a fresh `Storage` object per alias key even when two aliases share
  an identical params dict, this does *not* alias the same Python object across
  `storages["default"]` and `storages["public"]` — each is a separate `S3Storage`
  instance pointed at the same bucket/credentials, which is fine for correctness but
  matters for the "resolves to the same backend" check in §6 (compare resolved
  `bucket_name`/`endpoint_url`, not `is`).
- This preserves **exact** backward compatibility with the current five env vars: an
  existing single-bucket deployment that only sets `AWS_STORAGE_BUCKET_NAME` and friends
  continues to produce the same `default` entry as today (`_alias_storage_entry("AWS_S3")`
  reads `AWS_S3_*` per-alias vars first, which don't exist, then falls back to the
  unprefixed `AWS_STORAGE_BUCKET_NAME` etc.) — see §5 for why `"AWS_S3"` is chosen as the
  prefix passed for `default` rather than reusing `AWS_STORAGE_BUCKET_NAME` literally.
- Filesystem-only deployments (no bucket vars set anywhere) get
  `{"BACKEND": "django.core.files.storage.FileSystemStorage"}` for every alias,
  identical in spirit to today's `else` branch — `FileSystemStorage()` with no `location`
  kwarg uses `MEDIA_ROOT`/`MEDIA_URL` for every alias, i.e. all four logical buckets share
  one directory on disk, which is an acceptable degradation for local dev.
- The whole thing stays out of `settings_base.py`/dev settings — `config/settings_prod.py`
  is the only caller, matching the existing single-alias code's placement.

---

## 5. Env var naming

**One-line answer:** use a per-alias prefix that inserts the alias name between `AWS_S3`
and the field name (`AWS_S3_<ALIAS>_BUCKET_NAME`, etc.), keep the current five names
exactly as-is as the shared/default fallback (never rename them), and don't encode
staging/production in the var name at all — that axis is handled by which `.env` file or
secret store is loaded per environment, not by the variable name (12-factor: the same
var name, different value per deploy).

**Survey of conventions:**
- Django/12-factor convention is that environment identity (staging vs production) is
  external to the variable *names* — the same `DATABASE_URL`, `AWS_STORAGE_BUCKET_NAME`,
  etc. are set to different values in each environment's process environment / secrets
  manager. Baking `STAGING_` / `PROD_` prefixes into variable names is explicitly what
  12-factor warns against (config should vary by deploy, not by code/name) — see
  https://12factor.net/config. FLS already follows this: `settings_prod.py` reads plain
  `AWS_STORAGE_BUCKET_NAME`, and staging vs prod is a different value of the same var in
  a different environment, not a different var name.
- django-storages itself has no multi-bucket env var convention (there is no built-in
  multi-alias support pre-Django-4.2 `STORAGES`; historically people subclassed
  `S3Boto3Storage`/`S3Storage` per bucket and read bespoke settings — see
  https://github.com/jschneier/django-storages/issues/691 for the exact "how do I get
  two S3Storage instances with different settings" question, answered with "subclass and
  hardcode, or (post 4.2) use `STORAGES` `OPTIONS`").
- Common community pattern for "N buckets, shared credentials" is exactly the
  fallback-to-shared-var shape in §4: a specific var (`AWS_S3_MEDIA_BUCKET_NAME`) wins if
  set, otherwise a generic/shared var (`AWS_STORAGE_BUCKET_NAME`) is reused, keeping
  credentials (access key/secret) usually **not** duplicated per bucket at all (one IAM
  principal, scoped by bucket policy, reused across buckets) — which matches R2's typical
  setup (one R2 API token can be scoped to multiple buckets).

**Concrete table** (prefix inserted right after `AWS_S3` / `AWS`, alias name upper-cased
with `-` → `_`):

| Concept | Current (shared/default) | Per-alias pattern | Example: `learner-uploads` |
|---|---|---|---|
| Bucket name | `AWS_STORAGE_BUCKET_NAME` | `AWS_S3_<ALIAS>_BUCKET_NAME` | `AWS_S3_LEARNER_UPLOADS_BUCKET_NAME` |
| Access key | `AWS_S3_ACCESS_KEY_ID` | `AWS_S3_<ALIAS>_ACCESS_KEY_ID` | `AWS_S3_LEARNER_UPLOADS_ACCESS_KEY_ID` |
| Secret key | `AWS_S3_SECRET_ACCESS_KEY` | `AWS_S3_<ALIAS>_SECRET_ACCESS_KEY` | `AWS_S3_LEARNER_UPLOADS_SECRET_ACCESS_KEY` |
| Endpoint URL | `AWS_S3_ENDPOINT_URL` | `AWS_S3_<ALIAS>_ENDPOINT_URL` | `AWS_S3_LEARNER_UPLOADS_ENDPOINT_URL` |
| Region | `AWS_S3_REGION_NAME` | `AWS_S3_<ALIAS>_REGION_NAME` | `AWS_S3_LEARNER_UPLOADS_REGION_NAME` |
| Custom domain | `AWS_S3_CUSTOM_DOMAIN` | `AWS_S3_<ALIAS>_CUSTOM_DOMAIN` | `AWS_S3_LEARNER_UPLOADS_CUSTOM_DOMAIN` |
| Querystring auth | `AWS_QUERYSTRING_AUTH` | `AWS_S3_<ALIAS>_QUERYSTRING_AUTH` | `AWS_S3_LEARNER_UPLOADS_QUERYSTRING_AUTH` |
| Querystring expire | `AWS_QUERYSTRING_EXPIRE` | `AWS_S3_<ALIAS>_QUERYSTRING_EXPIRE` | `AWS_S3_LEARNER_UPLOADS_QUERYSTRING_EXPIRE` |

Rationale against the four requirements:
- **(a) Obviously per-alias:** the alias name sits in a fixed slot (`AWS_S3_<ALIAS>_...`)
  identical across all four aliases and all eight fields, easy to `grep AWS_S3_` and read
  off which alias each var belongs to.
- **(b) Shared-credentials shortcut:** kept via the fallback chain in §4 —
  `_alias_storage_entry` reads `AWS_S3_<ALIAS>_ACCESS_KEY_ID` first, and only if unset
  falls back to the existing unprefixed `AWS_S3_ACCESS_KEY_ID`. A deployment that reuses
  one R2 API token across all buckets sets the unprefixed credential vars once and never
  touches the per-alias credential vars.
- **(c) Staging vs production obvious:** deliberately *not* encoded in the name (see
  12-factor note above); the spec should not add a `STAGING_`/`PROD_` axis to these names.
  If FLS wants an explicit visual reminder of which environment a value belongs to,
  that's a `.env.staging` / `.env.production` file-naming concern, not a var-naming
  concern.
- **(d) Non-breaking:** every existing name (`AWS_STORAGE_BUCKET_NAME`,
  `AWS_S3_ACCESS_KEY_ID`, etc.) is preserved verbatim as the fallback tier; a project
  that has only ever set those five/six vars sees **zero required changes** — `build_storages()`
  (§4) reproduces exactly today's single-`default_storage`-for-everything behavior.

One asymmetry worth flagging for the spec to resolve explicitly: `AWS_STORAGE_BUCKET_NAME`
(bucket name) breaks the `AWS_S3_*` naming pattern the other six vars use (it's
`AWS_STORAGE_BUCKET_NAME`, not `AWS_S3_BUCKET_NAME`) — that's inherited from
boto3/django-storages' own historical `AWS_STORAGE_BUCKET_NAME` global setting name
(`storages/backends/s3.py:412`, `"bucket_name": setting("AWS_STORAGE_BUCKET_NAME")`), not
an FLS choice, so the per-alias table above normalizes the *new* per-alias name to
`AWS_S3_<ALIAS>_BUCKET_NAME` (matching the other six) while keeping the *shared fallback*
spelled `AWS_STORAGE_BUCKET_NAME` (matching what already exists). This mild inconsistency
should be called out in the spec rather than silently papered over.

---

## 6. Django system checks for storage configuration

**One-line answer:** checks can safely and cheaply verify "does this alias exist in
`settings.STORAGES`" (as `reports/checks.py` already does) and — more valuably — "does
resolving alias X produce the same effective bucket identity as resolving `default`",
entirely from already-loaded settings/resolved storage objects, with zero network calls;
what a check *cannot* safely verify without a network call is whether the bucket actually
exists or credentials are valid, so that stays out of scope for `checks`.

**What's safe to check (no network I/O):**
- Alias presence: `alias in settings.STORAGES` — string/dict membership, exactly the
  existing `freedom_ls_reports.W001` pattern (`freedom_ls/reports/checks.py:37-55`).
- Alias resolvability: `storages[alias]` doesn't raise `InvalidStorageError` — this
  additionally validates the `BACKEND` import string resolves, still no network call
  (`StorageHandler.create_storage` only does `import_string` + constructor, and
  `S3Storage.__init__`/`BaseStorage.__init__` do not make any network request — confirmed
  by reading `storages/base.py` and `storages/backends/s3.py:316-374`: constructing an
  `S3Storage` only builds a `botocore.config.Config` and, if CloudFront keys are set,
  parses a PEM key in-memory; boto3's actual `client('s3')` is created lazily via the
  `connection`/`unsigned_connection` properties, not in `__init__`).
- **"Same effective bucket as default" detection — the real danger signal.** Because
  constructing `storages[alias]` is safe and cheap (per above), a check can resolve both
  `storages["default"]` and `storages[alias]` and compare the attributes django-storages
  sets on the instance after `__init__` — `bucket_name`, `endpoint_url`, `region_name`,
  and (for R2, where multiple aliases might share one bucket but differ only by prefix)
  optionally `location`. E.g.:
  ```python
  @register()
  def check_learner_uploads_alias_not_default_bucket(**kwargs: object) -> list[CheckMessage]:
      """W00x: warn when the learner-uploads alias resolves to the same bucket/endpoint
      as default — the misconfiguration this whole feature exists to catch."""
      from django.core.files.storage import storages

      from freedom_ls.learner_management.config import config

      try:
          alias_storage = storages[config.LEARNER_UPLOADS_STORAGE_ALIAS]
          default_storage = storages["default"]
      except InvalidStorageError:
          return []  # covered by the presence check instead

      if not isinstance(alias_storage, S3Storage) or not isinstance(default_storage, S3Storage):
          return []  # e.g. both FileSystemStorage in dev — nothing to compare
      same_bucket = (
          getattr(alias_storage, "bucket_name", None) == getattr(default_storage, "bucket_name", None)
          and getattr(alias_storage, "endpoint_url", None) == getattr(default_storage, "endpoint_url", None)
      )
      if not same_bucket:
          return []
      return [Warning(
          f"{config.LEARNER_UPLOADS_STORAGE_ALIAS!r} resolves to the same bucket "
          f"({alias_storage.bucket_name}) as the default storage. Learner uploads "
          f"may be served with default's (possibly public) access settings.",
          hint="Point LEARNER_UPLOADS_STORAGE_ALIAS at a distinct, private bucket.",
          id="freedom_ls_learner_management.W00x",
      )]
  ```
  This is exactly the check that the existing `freedom_ls_reports.W001` (alias-presence
  only) does **not** perform, and it's the one that would have caught "alias declared but
  quietly pointed at the same public bucket as default." It's also a candidate to make an
  **Error**, not a `Warning`, for the learner-uploads alias specifically (PII), matching
  the severity discussion in §3.
- Cross-referencing `querystring_auth`: a check can further compare
  `getattr(alias_storage, "querystring_auth", None)` against what the alias's declared
  intent implies (e.g. "learner-uploads must be private" → assert `querystring_auth is
  True`), still zero network calls, all attribute reads on the already-constructed
  instance.

**What's out of scope for a check:** actually calling S3/R2 (`head_bucket`, listing,
etc.) to confirm the bucket exists or credentials are valid — that's a runtime/deploy-time
smoke test, not a `manage.py check`, because checks run in contexts (CI without network
egress, `--check` dry runs, etc.) where making real API calls is undesirable and would
turn a fast synchronous check into a slow, flaky, network-dependent one. Django's own
system-check docs recommend checks stay fast and side-effect-free
(https://docs.djangoproject.com/en/5.2/topics/checks/#writing-your-own-checks).

---

## 7. Per-alias `querystring_auth` / `custom_domain`

**One-line answer:** confirmed — both are plain per-instance constructor kwargs on
`S3Storage`, set independently for every alias via each alias's own `OPTIONS`, and two
`S3Storage` instances in the same process can and do hold different values simultaneously;
the one real gotcha is that django-storages' `get_default_settings()` still reads the
**global**, un-namespaced `AWS_S3_CUSTOM_DOMAIN` / `AWS_QUERYSTRING_AUTH` Django settings
as the *default* for any alias whose `OPTIONS` omits that key — so if a downstream project
(for legacy reasons, or a stray copy-paste) sets those as bare Django settings rather than
inside `OPTIONS`, every alias that doesn't explicitly override the option in its own
`OPTIONS` silently inherits that global value.

**Detail**, from `storages/base.py` (`BaseStorage.__init__`) and
`storages/backends/s3.py` (`S3Storage.get_default_settings`):

```python
class BaseStorage(Storage):
    def __init__(self, **settings):
        default_settings = self.get_default_settings()      # reads global AWS_* Django settings
        for name, value in default_settings.items():
            if not hasattr(self, name):
                setattr(self, name, value)                    # only if not already set
        for name, value in settings.items():                  # settings == OPTIONS passed in
            if name not in default_settings:
                raise ImproperlyConfigured(...)
            setattr(self, name, value)                         # UNCONDITIONALLY overrides
```
and
```python
def get_default_settings(self):
    return {
        ...
        "querystring_auth": setting("AWS_QUERYSTRING_AUTH", True),
        "custom_domain": setting("AWS_S3_CUSTOM_DOMAIN"),
        ...
    }
```
where `setting(name, default) = getattr(django.conf.settings, name, default)`
(`storages/utils.py:21-31`).

So: `get_default_settings()` is called fresh for *every* `S3Storage()` instantiation
(once per alias, since each alias gets its own instance per §2), reading whatever
`settings.AWS_QUERYSTRING_AUTH` / `settings.AWS_S3_CUSTOM_DOMAIN` currently resolve to as
Django settings — but the second loop in `BaseStorage.__init__` **always** overwrites
those attributes with whatever was passed as a keyword (i.e. whatever `OPTIONS` supplied
for that alias), because it iterates every key in the passed-in `settings` dict
unconditionally, with no "already set" guard (unlike the first loop). This confirms:

- Two aliases in one process, each with its own `OPTIONS = {"querystring_auth": True, ...}`
  vs `OPTIONS = {"querystring_auth": False, "custom_domain": "cdn.example.com", ...}`,
  coexist correctly — the values are set as plain instance attributes
  (`self.querystring_auth`, `self.custom_domain`) on two distinct `S3Storage` objects, no
  shared mutable state between them (confirmed no class-level `querystring_auth`/`custom_domain`
  attributes exist on `S3Storage` other than one irrelevant `querystring_auth = False`
  class attribute on an unrelated legacy subclass at `storages/backends/s3.py:713`, which
  doesn't affect `S3Storage` itself).
- **The gotcha:** `AWS_QUERYSTRING_AUTH` / `AWS_S3_CUSTOM_DOMAIN` etc. as **top-level
  Django settings** (not inside any `STORAGES[...]['OPTIONS']`) are still meaningful — they
  become the *default* fallback for `get_default_settings()` for **every** alias whose
  `OPTIONS` doesn't explicitly set that key. FLS's current `settings_prod.py` doesn't set
  any bare `AWS_QUERYSTRING_AUTH`/`AWS_S3_CUSTOM_DOMAIN` Django setting today — it only
  ever puts these values inside `OPTIONS` — so this gotcha is currently dormant, but the
  spec must ensure the new per-alias `build_storages()` helper (§4) **always populates
  `OPTIONS["querystring_auth"]` and `OPTIONS["custom_domain"]` explicitly for every
  alias** (even when the alias's value is "unset ⇒ default True / None", matching the
  existing `build_s3_media_storage` behavior of only setting `custom_domain` in `OPTIONS`
  when truthy) so that no alias ever silently falls through to a global — and the system
  check in §6 should also assert that no top-level `AWS_QUERYSTRING_AUTH`/`AWS_S3_CUSTOM_DOMAIN`
  Django setting is present, to prevent that footgun for downstream projects who might
  set them thinking they're a "global default" (they are, but one that competes silently
  with per-alias `OPTIONS`).

Docs / source: https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html ,
`.venv/lib/python3.13/site-packages/storages/base.py`,
`.venv/lib/python3.13/site-packages/storages/backends/s3.py:384-451`.

---

status: ok
