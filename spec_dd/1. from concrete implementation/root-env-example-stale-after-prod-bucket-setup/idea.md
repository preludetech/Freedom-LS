# Idea: FLS's root `.env.example` still documents the single-bucket storage layout

## The gap

Source: integrating `spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup` into this project.

`prod_bucket_setup` replaced one media bucket with six `STORAGES` aliases across three buckets, and
wrote a thorough annotated template for the new variables — but put it at
`spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/env_example`, inside the completed spec
directory. FLS's own root `.env.example` was never updated. It still carries the eight-variable
single-bucket block, and still describes the shared name as a switch:

```
# Cloudflare R2 (S3-compatible) media object storage
# config — also the on/off gate: unset uses local FileSystemStorage instead
AWS_STORAGE_BUCKET_NAME=
```

That comment is now the opposite of the advice the spec gives. `AWS_STORAGE_BUCKET_NAME` is no
longer a gate — `build_storages()` has no conditional — it is a shared fallback the spec explicitly
says to leave unset in production, because a per-bucket typo that falls through to it lands learner
data in the wrong bucket. `freedom_ls_deployment.E003` exists specifically to catch the
configuration the root `.env.example` still recommends.

A downstream copying the root `.env.example` (the obvious thing to do, and what this project's own
`.env.example` was derived from) therefore gets a layout the deploy checks reject, and has no
pointer to the good template buried in `spec_dd/3. done/`.

## Expected fix

Port the storage section of the spec's `env_example` into FLS's root `.env.example`. A completed
spec directory is an archive; the root template is what downstreams actually copy, so anything a
spec changes about deployment configuration needs to land there before the spec is closed. Worth
considering as a checklist item in `/update_upgrade_notes`.

## Sources

- `submodules/Freedom-LS/.env.example` — lines 82-98, the stale block.
- `submodules/Freedom-LS/spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/env_example` — lines
  82-168, the good template.
- `submodules/Freedom-LS/freedom_ls/deployment/checks.py` — E003.
