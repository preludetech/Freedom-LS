---
name: reference-report-org-branding-qa-setup
description: The per-organisation report-branding QA seed (branch report-rendered-with-org-name) — the twelve orgs, the slug drift that trips --organisation-slug, and why Cohort has no slug
metadata:
  type: reference
---

Plan: `spec_dd/2. in progress/report-rendered-with-org-name/3. frontend_qa.md`.
Shape: one `standard-cohort-medium-course` fixture cohort per Organisation, so
the same report can be regenerated under a dozen different brand slots.

Recipe (all idempotent):

```
uv run python manage.py qa_create_organisations DemoDev            # POSITIONAL, see below
uv run python manage.py qa_create_report_brand_organisations DemoDev
# then, once per org slug, plus ONCE WITH NO --organisation-slug (house org):
uv run python manage.py qa_create_report_fixtures \
    --only standard-cohort-medium-course --organisation-slug <slug>
```

## The plan's command 1 is wrong

`qa_create_organisations --site-name DemoDev` exits with
`Error: No such option: --site-name`. Positional. See
[[reference_qa_command_site_arg_styles]].

## Slug drift on the dev DB — do NOT guess a slug from the name

Earlier QA passes renamed organisations, and `Organisation.slug` is assigned
once at creation and never re-derived. On this DB:

| name | slug |
|---|---|
| `Northside` | **`northside-2`** |
| `Northside Academy of Technology` | **`northside`** |
| `RPAS Training` | `rpas-training` |
| `RPAS Training Academy` | `rpas-training-academy` (holds the 11-fixture matrix) |
| `Восточно-Европейская Академия Непрерывного Образования` | **Cyrillic slug**, not `qa-non-latin-academy` |

The Cyrillic row predates `_ensure_organisation`'s `slug_base=` fix, so it kept a
unicode slug. Harmless for the reports admin, but `educator_interface` routes on
`[-a-zA-Z0-9_]+`, so that org is a NoReverseMatch for any educator in it.
Always dump `(name, slug)` from the DB before building the `--organisation-slug`
loop.

## Cohort has NO slug field

`freedom_ls.learner_management.models.Cohort` has `organisation`, `name`, no
slug. The "cohort slug" in a download filename is computed at request time by
`freedom_ls/reports/views.py`:

```python
f"{slugify(report.cohort.organisation.name, allow_unicode=True)}-"
f"{slugify(report.cohort.name, allow_unicode=True)}-progress-report.pdf"
```

It slugifies the **organisation NAME, not its slug**, so the Cyrillic filename
test passes regardless of the drifted slug — and `---` (punctuation-only name)
slugifies to `""`, giving a filename that *starts with a hyphen*:
`-qa-report-standard-cohort-progress-report.pdf`.

## The dropdown is FLAT, not grouped

QA plans say "cohorts are grouped by organisation name". They are not:
`CohortChoiceField.label_from_instance` returns `f"{org.name} — {cohort.name}"`
(em dash) in one flat `<select>`, ordered `organisation__name, name`. And
`all_cohorts_visible_to(superuser)` is **not site-scoped** — a superuser's
dropdown also lists Bloom / Demo / Prelude / Wrend cohorts, including a
`Demo — Cohort 2025.03.04` that reads almost identically to the DemoDev one.

## Every org's cohort has the SAME name

`QA Report Standard Cohort` exists once per organisation (the unique constraint
is `(site, organisation, name)`). Pick by the organisation half of the label.

## Legacy learners inflate the fixture cohorts

Cohorts built before `organisation_email_prefix` existed still hold the
un-namespaced `qa-report-std-NN@email.com` users (and `qa-report-defaultorg-NN@`
in the house org) *alongside* the new `qa-report-std-<org-slug>-NN@` set. Those
cohorts read 18 (or 27) members instead of 9, and the legacy Users are shared
across many organisations' cohorts. Re-running the command does not clean them:
`_reset_fixtures` only matches the namespaced prefix, and only under `--reset`.
Harmless for branding QA; state the real counts in the report.

## Grants accumulate

`qa-report-restricted@email.com` ends up with guardian `view_cohort` on EVERY
`QA Report Standard Cohort` (14 of them here), and
`qa-report-orgstaff@email.com` with `organisation_staff` on every organisation
the command was ever pointed at. "Cohort B" for a 403 check must therefore be a
different *fixture key* (e.g. `QA Report Tiny Cohort`), never another org's
standard cohort. See [[reference_report_fixture_commands]].

## QA Dual Logo on disk

`organisation_logo_upload_to` keys on the pk and the dark variant appends
`-on-dark`:

```
media/organisations/<uuid>.png           # logo            <- fc-light-bg.png
media/organisations/<uuid>-on-dark.png   # logo_on_dark    <- fc-dark-bg.png
```

Two genuinely distinct files (md5s differ); fixtures live in
`freedom_ls/qa_helpers/fixtures/`. `QA Logo Vanish`'s file is usually already
gone — an earlier pass deleted it by hand and the command never puts it back.
