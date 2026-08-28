# FLS Plugin Configuration

## Dev Credentials
- Admin email: demodev@email.com
- Admin password: demodev@email.com  # pragma: allowlist secret

## Project Settings
- Base URL: http://127.0.0.1:8000

## QA Dev Data

The commands `/fls-dev:do_qa` runs to reset development data mid-run. Each value is a shell command
run from the project root. Leave a value blank if this project has no such step, and `do_qa` skips
that rung and falls through to the next. Every command must be non-interactive, so keep its
`--yes` / `-y` / `--noinput` flag in the value.

Seeding is not configured here. The seed list comes from the test plan's own `§0`.

- Content reset: uv run python manage.py danger_content_delete --yes
- DB drop: .claude/fls-dev/scripts/dev_db_delete.sh
- DB create: .claude/fls-dev/scripts/dev_db_init.sh
- Migrate: uv run python manage.py migrate
