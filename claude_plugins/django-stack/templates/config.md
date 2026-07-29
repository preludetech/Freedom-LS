# django-stack (ds) Plugin Configuration

Written by `/ds:init` with portable defaults. Review and edit every value — these are a starting
point, not a description of this project.

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

- Admin theme: standard
- Object permissions (django-guardian): disabled
