# Notes for the spec

Constraints and decisions the spec shouldn't have to rediscover. See `idea.md` for the layout
itself and why it is shaped that way.

## Settings layer

A `build_storages()` helper in `freedom_ls/deployment/storage.py` that **always emits every alias
key**, resolving each from per-alias env vars, falling back to the shared
`AWS_STORAGE_BUCKET_NAME` credentials, and falling back again to `FileSystemStorage` when no bucket
is configured. `build_s3_media_storage()` is already alias-agnostic and becomes its single-alias
building block, unchanged.

The per-alias env-var naming scheme needs to keep the shared-credentials shortcut, make staging
versus production obvious at a glance, and not break downstream deployments already setting the
current names.

Declare the `reports` alias in FLS's own production settings. Add aliases for organisation logos
and for `content_engine.File`, matching the `REPORTS_STORAGE_ALIAS` pattern. `content_engine`
already has `config.py` and `checks.py` to extend; `organisations` has neither and needs both
created.

## System check

Today's `freedom_ls_reports.W001` only detects a wholly undeclared alias. Under the
always-declared design that becomes the normal unconfigured state, so the check stops catching
anything. Replace it with one that compares **resolved bucket names** and fires when a
privacy-sensitive alias resolves to the same bucket as `default`.

## Model fields

Every per-field storage assignment goes through a **named module-level callable**. Never a bare
`Storage(...)` instance, because django-storages is `@deconstructible` and bucket names and
credentials would freeze into migration history. Never a lambda, because it can't be serialised.

Adding `storage=` to the two fields that lack it generates one `AlterField` migration each. Those
reference only the callable's dotted path, so later bucket changes need no migration.

## R2 details that will bite

- `Cache-Control` is per-object metadata set at upload. There is no bucket default, so the public
  bucket gets none of its caching benefit unless the upload path sets the header.
- Presigned URLs max out at 7 days and can't be used with custom domains.
- POST-based (HTML form) presigned uploads are not supported. An S3 `createPresignedPost`-style
  browser upload will not work.
- Bucket Locks block emptying or deleting a locked bucket, which matters for any staging
  environment that mirrors production's rules.

## Bucket creation decisions

These have to be made before the first production deploy rather than discovered after it: final
bucket names, jurisdiction (immutable at creation), the custom domain for `fls-prod-public`, and
how many API tokens exist and which buckets each is scoped to.

## Documentation and downstream

- The env-var table in `docs/deployment-security-checklist.md` is already incomplete. It omits
  `AWS_S3_CUSTOM_DOMAIN`, `AWS_QUERYSTRING_AUTH`, `AWS_QUERYSTRING_EXPIRE` and
  `REPORTS_STORAGE_ALIAS`.
- `docs/product/deployment.md` and `docs/product/security-and-data-handling.md` both need updating.
  The latter currently reassures the reader about a mechanism FLS's own production settings don't
  use.
- `claude_plugins/fls-dev/resources/template_repo_manifest.md` audits downstream projects against
  the single-bucket shape and needs to grow to N aliases.
- `upgrade_notes.md` for downstream projects, following the `basic_reports` precedent, times three
  new aliases.

## A new `file-storage` skill

Four buckets are only worth having if new file fields land in the right one, and that decision gets
made the moment someone adds a `FileField` or `ImageField`, which is exactly when nobody re-reads a
spec. Add a skill to `claude_plugins/fls-dev/skills/`, following the shape of `multi-tenant` and
`app-settings`. It should describe each bucket and what belongs in it, give the decision rule (who
supplies the bytes, how do they reach the browser, can they be regenerated), and carry the
mechanical rules above. Its `description` must trigger on creating or modifying a model file or
image field, so it fires without being asked for.

## Admin as a read path

`FileAdmin` and `OrganisationAdmin` both expose the raw field, so Django's `ClearableFileInput`
renders a `Currently:` link against `.url`. Reports deliberately don't;
`reports/tests/test_admin.py` asserts `report.file.url` never appears in the changelist. Confirm
that the staff-only signed-URL surface is acceptable for the other two rather than assuming the
admin never touches storage URLs.
