---
name: reference-report-brand-organisations-command
description: qa_create_report_brand_organisations — the extra orgs for report cover/footer branding QA, incl. the punctuation-only slug trap and the two deliberately-broken logos
metadata:
  type: reference
---

`uv run manage.py qa_create_report_brand_organisations [SITE_NAME]`
(positional site, default DemoDev — same style as its sibling
`qa_create_organisations`). Idempotent; never replaces a logo that is already
set, because QA deletes one of them by hand.

Seeds six Organisations that `qa_create_organisations` does not cover:

| name | slug | chars | logo |
|---|---|---|---|
| `Riverbend Institute of Applied Technology Ltd` | `riverbend-institute-of-applied-technology-ltd` | 45 | no |
| `Lakeside College of Health Sciences Inc.` | `lakeside-college-of-health-sciences-inc` | 40 | no |
| `Acme & Sons <b>Ltd</b> "Trading"` | `acme-sons-bltdb-trading` | 32 | no |
| `---` | `qa-punctuation-only` | 3 | no |
| `QA Logo Vanish` | `qa-logo-vanish` | 14 | yes (real webp) |
| `QA Bad Logo` | `qa-bad-logo` | 11 | yes (ASCII text named .png) |

## Gotchas

- **A punctuation-only name slugifies to the empty string.** `slugify("---")`
  is `""`, and an empty slug is *falsy*, so `--organisation-slug ""` makes
  `qa_create_report_fixtures` silently fall back to the site's default
  organisation instead of erroring. `_ensure_organisation` in
  `qa_create_organisations` therefore takes an optional `slug_base=` override;
  this command passes `qa-punctuation-only`.
- **Attaching a non-image logo needs `FieldFile.save()`, not `full_clean()`.**
  `validate_organisation_logo` decodes the bytes with Pillow and would reject
  it; `.save()` goes through `Model.save()`, which never calls `full_clean()`.
  That is exactly the state a pre-validator upload left rows in, and it is what
  exercises the report's render-time fallback.
- `Organisation.initials` returns **None** for `---` (no alphabetic character),
  so the monogram fallback has to fall back again.
- `organisation_logo_upload_to` keys on the pk, so the absolute path is
  `MEDIA_ROOT/organisations/<uuid><ext>` — hand QA that path when the scenario
  is "delete the file behind the record".
