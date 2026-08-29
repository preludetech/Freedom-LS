---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - STORAGES                          # hard: public, course_media and reports must be declared or model import raises ImproperlyConfigured; user_uploads and certificates surface as E001 instead
  - REPORTS_STORAGE_ALIAS             # hard: the silent fallback to 'default' is gone
  - CONTENT_MEDIA_STORAGE_ALIAS       # optional: new, defaults to "course_media"
  - ORGANISATION_LOGO_STORAGE_ALIAS   # optional: new, defaults to "public"
  - SILENCED_SYSTEM_CHECKS            # optional: drop any freedom_ls_reports.W001 entry; E001 to E004 are all silenceable
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: prod_bucket_setup

FLS media no longer lives in one bucket. Five media aliases now resolve independently, each from its
own environment variables, and the models that own file fields name an alias instead of writing to
`default`. The five are `public`, `course_media`, `user_uploads`, `reports` and `certificates`. Those
five plus `default` are the six `STORAGES` keys that resolve from `AWS_*` variables; `staticfiles` is
the seventh key and never does. In production the five media aliases sit on three real buckets, and
`default` resolves to a fourth bucket name that is deliberately never created.

## Breaking changes

**`settings.STORAGES` must declare every alias.** `Organisation.logo`, `content_engine.File.file` and
`GeneratedReport.file` now pass a `storage=` callable that resolves an alias by name. A callable
`storage=` runs once, at model import, so an alias your settings module does not declare raises
`ImproperlyConfigured` while Django is importing models. The message names the missing alias and the
setting that chose it. The project does not boot, and the test suite does not collect. That is
`public`, `course_media` and `reports`, the three aliases a field names today. `user_uploads` and
`certificates` have no field yet, so an undeclared one of those surfaces under `check --deploy` as an
E001 rather than at boot. Declare all five, alongside `default` and `staticfiles`.

**The reports storage fallback is gone.** `get_reports_storage()` used to swallow
`InvalidStorageError` and fall back to `storages["default"]`. A project that never configured
`REPORTS_STORAGE_ALIAS` booted fine and wrote cohort report PDFs, which carry learner names and quiz
answers, to whatever `default` pointed at. It now fails at import instead. The startup failure names
the missing key, which is the whole point of the change.

**`manage.py check --deploy` gains four errors.** `freedom_ls_deployment.E001` fires when a media
alias resolves to the same bucket as `default`. `freedom_ls_deployment.E002` fires when a media alias
resolved to no bucket at all and fell back to local filesystem storage while `DEBUG` is off.
`freedom_ls_deployment.E003` fires when a media alias took its bucket from the shared
`AWS_STORAGE_BUCKET_NAME` because its own `AWS_S3_<PURPOSE>_BUCKET_NAME` is not set.
`freedom_ls_deployment.E004` fires when an alias holding private files serves unsigned URLs, which
covers `course_media`, `user_uploads` and `reports`.

How many you see on the first `check --deploy` depends on where you are upgrading from, so there is
no single number. Set no `AWS_*` variable at all and every alias drops to local disk, which fires
five E002, one per media alias. Keep only the shared `AWS_STORAGE_BUCKET_NAME` set, the usual day-one
state for a project coming off the single-bucket layout, and every media alias both resolves where
`default` does and inherits that bucket from the shared name. That fires ten errors, five E001 and
five E003, one pair per alias. Work through manual steps 1 to 8 and the count reaches zero. Zero is
the only unconditional number here, and the one to converge on.

All four checks are `deploy=True`, so plain `check`, `runserver`, `migrate` and pytest never run
them. If your deployment serves media from local disk deliberately, silence E002 through
`SILENCED_SYSTEM_CHECKS` and keep the other three.

Six per-bucket variables do not mean six new buckets. Two pairs of aliases share a bucket on purpose:
`public` and `certificates` both point at the anonymously readable branding bucket, and `reports` and
`user_uploads` both point at the learner-data bucket. Six variables, four bucket names, three real
buckets.

**Cohort report PDFs move to a new key prefix.** `report_upload_path` returns
`cohort_reports/{pk}-cohort-report.pdf` instead of `reports/{pk}-cohort-report.pdf`. The prefix keeps
report keys clear of `user_uploads/` in the shared learner-data bucket and is what an R2 lifecycle
expiry rule attaches to. Rows written before the upgrade keep their stored `reports/...` name and
still download; only new reports use the new prefix. If you are also repointing the `reports` alias
at a different bucket, those older files stop resolving unless you copy them across.

**`freedom_ls_reports.W001` is gone.** It warned that `REPORTS_STORAGE_ALIAS` named no key in
`STORAGES`, which is now a boot failure rather than a warning. The check is deleted outright and the
id is not held in reserve, so a later reports check may take the number. Remove the entry from
`SILENCED_SYSTEM_CHECKS` (manual step 4).

## Manual steps

1. Run `uv run manage.py migrate`. Two `AlterField` migrations record the new `storage=` callables:
   `freedom_ls_content_engine.0017_alter_file_file` and
   `freedom_ls_organisations.0003_alter_organisation_logo`. Neither touches data.

2. Rebuild your production `STORAGES` from `build_storages()`:

   ```python
   from freedom_ls.deployment.storage import build_storages

   STORAGES = build_storages(
       staticfiles={"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
   )
   ```

   It emits all seven keys unconditionally and resolves each from its own environment variables. Pass
   `reports_alias=` if your project overrides `REPORTS_STORAGE_ALIAS`.

3. Declare the same seven keys in your base or development settings too, pointing every alias at the
   stock `django.core.files.storage.FileSystemStorage`. Without an explicit `location` they all
   follow `MEDIA_ROOT`, which is what keeps a test suite's tmp-dir isolation working. Copy the
   `STORAGES` block from `config/settings_base.py`. The `public` entry is the one that differs. It
   carries `OPTIONS: {"allow_overwrite": True}` so a replaced organisation logo overwrites its stable
   `organisations/{pk}{ext}` key locally the way it does on S3. No other alias takes an `OPTIONS` key.

4. Drop `"freedom_ls_reports.W001"` from `SILENCED_SYSTEM_CHECKS` if your project silences it.
   Django ignores an id no check emits, so a stale entry costs nothing today, but the id is free to
   be reused and a leftover entry would silence whatever check claims it next.

5. Create the buckets and set the environment variables. Each property resolves from
   `AWS_S3_<PURPOSE>_<PROPERTY>` first, then the shared `AWS_*` variable. `PURPOSE` is one of
   `PUBLIC`, `COURSE_MEDIA`, `USER_UPLOADS`, `GENERATED`, `CERTIFICATES`, `DEFAULT`. Set all six
   bucket-name variables, `AWS_S3_DEFAULT_BUCKET_NAME` included, and leave the shared
   `AWS_STORAGE_BUCKET_NAME` unset. With no shared fallback in place, a typo in a per-bucket name
   drops that alias to local disk where E002 catches it, rather than quietly writing to the wrong
   bucket. The annotated template is the repo root `.env.example`; the copy this spec shipped is at
   `spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/env_example`.

6. Set `AWS_S3_PUBLIC_QUERYSTRING_AUTH=false` and `AWS_S3_CERTIFICATES_QUERYSTRING_AUTH=false` per
   alias if you serve branding publicly. Never use the shared `AWS_QUERYSTRING_AUTH` form for this:
   it reaches all five media aliases, two of which hold personal data. E004 catches this too, over
   `course_media`, `user_uploads` and `reports`, so the manual step is defence in depth rather than
   the only guard.

7. Add `manage.py check --deploy` to your deploy pipeline if it is not there already. Nothing else
   runs E001, E002, E003 or E004.

8. Audit your own `FileField` and `ImageField` definitions. Any field without an explicit `storage=`
   still writes to `default`, which under this layout is a bucket nothing should ever write to. The
   `fls-dev:file-storage` skill covers which alias a new file field belongs in.
