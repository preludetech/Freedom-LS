---
name: reference-admin-constraint-fixtures-command
description: qa_create_admin_constraint_fixtures — webhook endpoints/secrets, CourseInterest, second-org Learner and per-org cohorts for the uniqueness-constraint admin QA pass; the WebhookSecret name regex trap
metadata:
  type: reference
---

`uv run python manage.py qa_create_admin_constraint_fixtures [SITE_NAME]`
(positional, **default `DemoDev`**). Idempotent — a re-run prints `kept` for every row.

File: `freedom_ls/qa_helpers/management/commands/qa_create_admin_constraint_fixtures.py`.

Written Aug 2026 for the `final_pre_deploy_db_structure_cleanup` browser QA pass. The
unifying theme is "a row that already exists so the tester can try to DUPLICATE it in the
admin and watch the constraint fire".

## What it seeds (all on one site)

| Row | Natural key / constraint |
|---|---|
| `WebhookSecret qa_hook_api_key` | referenced by endpoint one's `headers_template` |
| `WebhookSecret qa_existing_secret` | `unique_webhook_secret_name_per_site` |
| `WebhookEndpoint https://example.invalid/hooks/one` | templated (POST/json, `auth_type="none"`) |
| `WebhookEndpoint https://example.invalid/hooks/two` | plain, `auth_type="signing"` |
| `CourseInterest demodev_s2 -> standard-markdown-demo-finance` | `unique_course_interest` |
| `Learner demodev_s2 @ RPAS Training` | `unique_learner_per_organisation` |
| `Cohort "QA Org Scope Cohort"` in RPAS Training | `unique_cohort_name_per_organisation` |
| `Cohort "QA Northside Cohort"` in Northside | gives a 2nd non-default org a cohort |

Deliberately creates **no** `WebhookDelivery` — those come from the admin "Send Test" action.

## TRAP — `WebhookSecret.name` forbids hyphens

`SECRET_NAME_VALIDATOR = RegexValidator(r"^[a-zA-Z_][a-zA-Z0-9_]*$")`
(`freedom_ls/webhooks/models.py`). QA plans keep asking for a secret named
`qa-existing-secret`. Factories skip `full_clean()`, so such a row *would* insert — but the
admin add form then rejects the hyphenated name on the **regex** before it ever reaches the
uniqueness check, so the duplicate-name test fails for the wrong reason. Always seed the
underscore form (`qa_existing_secret`) and say so.

Proven with a rolled-back form probe:

```
WebhookSecretForm(data={"name": "qa_existing_secret", ...}).errors
  -> __all__: "Webhook secret with this Site and Name already exists."
WebhookSecretForm(data={"name": "qa-existing-secret", ...}).errors
  -> name: "Name must start with a letter or underscore ..."
```

## Endpoint <-> secret has NO FK

The only association is by **name inside a Jinja2 template**
(`{{ secrets.<name> }}` in `body_template` / `headers_template`), resolved at render time by
`webhooks/rendering.py::build_template_context`. `WebhookEndpoint.clean()` runs
`_validate_referenced_secrets_exist()`, so **create the secret before the endpoint** or the
endpoint will not validate.

Other `clean()` rules worth knowing:
- Setting ANY of `http_method` / `content_type` / `headers_template` / non-`signing`
  `auth_type` makes `body_template` **required**.
- `content_type="application/json"` means the rendered body must parse as JSON.
- SSRF/HTTPS checks are `if not settings.DEBUG`, so `*.invalid` hosts are fine in dev.

The command calls `endpoint.full_clean()` **before** `save()` (build-then-clean-then-save)
so a fixture the admin would refuse to re-save never lands in the DB.

## mypy + ruff on qa commands

- `cast(Model, SomeFactory(...))` is the house pattern (see `qa_create_site_scoping_form`);
  without it mypy reports `Incompatible return value type (got "XFactory")`.
- ruff `S105` fires on module constants whose NAME contains `SECRET`/`TOKEN` even when the
  value is just an identifier. `# noqa: S105` on the line; a bare `# noqa` comment line
  trips `RUF100`.
