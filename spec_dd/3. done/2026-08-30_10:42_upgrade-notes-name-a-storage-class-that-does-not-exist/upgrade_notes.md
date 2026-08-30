---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: correct the stale storage docs, and close the drift window

No shipped code changed. Nothing under `freedom_ls/` or `config/` was touched, no migration was
added, and no dependency moved. This branch corrects documentation: the upgrade notes shipped with
the `prod_bucket_setup` spec, which told you to do several things that were wrong, and the repo root
`.env.example`, which never learned about the multi-bucket storage layout.

If you have not yet integrated `prod_bucket_setup`, read the corrected instructions below before you
do. If you already integrated it, check your settings against them.

## Breaking changes

None.

## Manual steps

The five corrections below replace what
`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/upgrade_notes.md` originally said. That file is
now correct in place, but a downstream project checks the FLS submodule out at each spec's completion
commit, so integrating `prod_bucket_setup` still shows you the stale text. These notes are the route
by which the fix reaches you.

1. **The `public` storage backend is stock Django, not an FLS class.** The old notes told you to
   point the `public` alias at `freedom_ls.deployment.storage.OverwritingFileSystemStorage`. No such
   class exists. It was deleted by a PR-review fix hours after those notes were written. Use
   `django.core.files.storage.FileSystemStorage` with `OPTIONS: {"allow_overwrite": True}` instead,
   which is what `config/settings_base.py` declares. `allow_overwrite` is what makes a replaced
   organisation logo land on its existing `organisations/{pk}{variant}{ext}` key rather than beside
   it. The same notes also said no alias carries an `OPTIONS` key; `public` does, and it is the only
   one that does.

2. **`manage.py check --deploy` gains four errors, not two.** The old notes named
   `freedom_ls_deployment.E001` and `freedom_ls_deployment.E002` only. `freedom_ls_deployment.E003`
   fires when a media alias took its bucket from the shared `AWS_STORAGE_BUCKET_NAME` because its own
   `AWS_S3_<PURPOSE>_BUCKET_NAME` is unset. `freedom_ls_deployment.E004` fires when an alias holding
   private files serves unsigned URLs, covering `course_media`, `user_uploads` and `reports`. All
   four are ordinary `deploy=True` checks, and all four are silenceable through
   `SILENCED_SYSTEM_CHECKS`; the old notes singled out E002 as the silenceable one. A pipeline that
   passed on the two ids it knew about is not a pipeline that passed.

3. **Set six bucket-name variables, not five.** `AWS_S3_DEFAULT_BUCKET_NAME` is one of them. `PURPOSE`
   is one of `PUBLIC`, `COURSE_MEDIA`, `USER_UPLOADS`, `GENERATED`, `CERTIFICATES` or `DEFAULT`. Six
   variables do not mean six buckets: `public` and `certificates` share the branding bucket,
   `reports` and `user_uploads` share the learner-data bucket, and the name behind
   `AWS_S3_DEFAULT_BUCKET_NAME` is deliberately never created, so a write that reaches `default`
   fails instead of landing learner data somewhere unintended. Six variables, four names, three real
   buckets.

4. **Coming off the single-bucket layout, expect ten errors, not five.** The old notes gave one
   blanket count. The count depends on where you start. With no `AWS_*` variable set at all, every
   alias drops to local disk and you get five E002, one per media alias. With only the shared
   `AWS_STORAGE_BUCKET_NAME` set, which is the usual day-one state, every media alias both resolves
   where `default` resolves and inherits that shared name, so you get ten errors: five E001 and five
   E003, one pair per alias. Zero is the only count that holds unconditionally, and it is the one to
   converge on.

5. **Re-copy the storage block from the repo root `.env.example`.** It previously shipped the
   single-bucket block, declared no per-purpose bucket variables, and described
   `AWS_STORAGE_BUCKET_NAME` as an on/off gate that switches storage to local `FileSystemStorage`
   when unset. It is no such gate. Each alias resolves its bucket independently, from its own
   `AWS_S3_<PURPOSE>_BUCKET_NAME` first and the shared name only as a fallback, and only an alias
   that ends up with no name from either drops to local `FileSystemStorage`. The guidance is the
   opposite of what the old comment implied: leave the shared name unset in production so a
   misspelled per-bucket variable drops that one alias to local disk where E002 catches it, rather
   than writing silently to the wrong bucket. The file now also warns that the
   shared `AWS_QUERYSTRING_AUTH=False` form reaches all five media aliases, two of which hold
   personal data. Set `AWS_S3_PUBLIC_QUERYSTRING_AUTH` and `AWS_S3_CERTIFICATES_QUERYSTRING_AUTH` per
   alias instead.

**If you already integrated `prod_bucket_setup` and your project stopped booting**, step 1 is your
fix. A callable `storage=` resolves at model import, so the missing class fails while Django is still
importing models: your project does not start and your test suite does not collect. The exception you
see is `ImproperlyConfigured: settings.STORAGES has no 'public' entry, named by
ORGANISATION_LOGO_STORAGE_ALIAS`, which is misleading, because the entry is present and it is the
`BACKEND` dotted path inside it that does not import. The chained cause names the real problem:
`Module "freedom_ls.deployment.storage" does not define a "OverwritingFileSystemStorage"
attribute/class`. Replace that `BACKEND` with `django.core.files.storage.FileSystemStorage` and keep
the `OPTIONS` value.
