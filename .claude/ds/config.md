# django-stack (ds) Plugin Configuration

## Project Settings

- Dev base URL: http://127.0.0.1:8000

## Dev Credentials

Login for the local development site, read by `ds:use-playwright`. Leave both blank if the dev site
needs no login; the skill will ask. Never record a non-local credential here — this file is
committed. Machine-specific values belong in `.claude/ds/config.local.md`, which is gitignored and
takes precedence over this file.

- Admin email:
- Admin password:

## Alpine.js
- CSP build: enabled

## Admin

- Admin theme: unfold
- Object permissions (django-guardian): enabled

## Rebase Scripts

Run by `/ds:rebase_main` after a rebase and before the tests. Leave a value blank if this
project has no such step.

- Rebuild script: .claude/fls-dev/scripts/rebuild_after_rebase.sh

## Test Tiers

Whether a full tier runs `[tool.test_tiers.remote] command` from `pyproject.toml`, when the project
sets one, or the local full command. `off` runs every full tier locally, without touching the
remote table. Set it in `.claude/ds/config.local.md` to switch it for one machine only.
`DS_TEST_REMOTE=on|off` in the environment overrides both files for one run.

- Remote full run: on
