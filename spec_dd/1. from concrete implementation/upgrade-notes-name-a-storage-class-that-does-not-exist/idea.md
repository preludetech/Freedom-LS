# Idea: `prod_bucket_setup` upgrade notes name a storage class that does not exist

## The bug

Source: integrating `spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup` into this project.

Manual step 3 of `upgrade_notes.md` tells downstream projects to copy the `STORAGES` block into
their own base settings, and says of the `public` entry:

> ...which uses `freedom_ls.deployment.storage.OverwritingFileSystemStorage` rather than the stock
> backend so a replaced organisation logo overwrites its stable `organisations/{pk}{ext}` key
> locally the way it does on S3.

That class does not exist. `git grep OverwritingFileSystemStorage c43a3381 -- freedom_ls/ config/`
returns nothing. The shipped `config/settings_base.py:284-287` uses the stock backend with an
option instead:

```python
ORGANISATION_LOGO_STORAGE_ALIAS: {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {"allow_overwrite": True},
},
```

The prose looks like it was written against an earlier draft and not refreshed after
`43a8e0ea` ("fix(qa): make the public alias overwrite at its stable key") replaced the custom class
with `allow_overwrite`.

This fails hard, not subtly. A `storage=` callable resolves at model import, so a downstream that
follows the prose literally gets an import error on the dotted path the moment Django imports
`Organisation` — the project does not boot and the test suite does not collect. The correct value
is also not guessable from the notes alone.

## Expected fix

Correct manual step 3 in the spec's `upgrade_notes.md` to describe the `allow_overwrite` option and
drop the reference to `OverwritingFileSystemStorage`. Worth a wider check that nothing else written
during that spec still refers to the deleted class.

## Sources

- `submodules/Freedom-LS/spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/upgrade_notes.md` —
  manual step 3.
- `submodules/Freedom-LS/config/settings_base.py` — lines 284-287, the shipped form.
- `submodules/Freedom-LS/claude_plugins/fls-dev/resources/template_repo_manifest.md` — line 134,
  which describes `allow_overwrite` correctly.
