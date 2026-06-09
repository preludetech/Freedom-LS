# Dev email viewer — Mailpit

## Goal

Give developers and demo presenters a polished web inbox to view the emails the
application sends during development, using a dedicated email-testing tool.

## Approach

Run [Mailpit](https://mailpit.axllent.org/), an open-source email-testing tool.
Mailpit runs a local SMTP server that captures outgoing mail and exposes a
modern web interface (search, HTML / plain-text / raw views, responsive
preview).

In development, point Django's email backend at Mailpit's SMTP server. Captured
email is then browsed in Mailpit's web UI rather than inside Django.

## Scope

- Add Mailpit as a service in the existing `dev_db/docker-compose.yaml`, so it
  starts alongside Postgres and is shared by all worktrees (the same way the
  shared Postgres container is). One Mailpit instance serves every branch; no
  per-branch inbox separation, since this is for development/demo only.
- Mailpit runs with no persistent volume — captured mail is ephemeral and clears
  when the container restarts.
- Use Mailpit's default ports: `1025` for SMTP, `8025` for the web inbox.
- Configure the development `EMAIL_BACKEND` / SMTP settings in
  `config/settings_dev.py` to send to Mailpit's SMTP listener on
  `localhost:1025`. This replaces the current file-based backend
  (`filebased.EmailBackend` writing to `gitignore/emails`).
- Document how to start Mailpit (via `dev_db`) and open its web inbox during a
  demo.
- Update the existing docs that describe the old file-based dev-email preview so
  they no longer contradict the new Mailpit flow:
  - the root `README.md` note about emails being saved in `gitignore/emails`, and
  - the "Previewing Emails in Development" section of
    `fls-claude-plugin/resources/email_templates.md`.

## Out of scope

- Any change to production email sending.
- Bundling or vendoring the Mailpit binary into the repository.
- Persisting captured email across container restarts.
- Per-branch / isolated inboxes.

## Acceptance criteria

- With Mailpit running, triggering an email-sending flow in development results
  in a message that appears in the Mailpit web inbox.
- The HTML, plain-text, and raw views of an email are all viewable.
- Production email behaviour is unchanged.
- Starting Mailpit and reaching its inbox is documented and repeatable.
- No remaining documentation tells developers to look in `gitignore/emails` for
  dev emails; all dev-email-preview docs point at Mailpit.

## Decisions

- Mailpit is added to the existing `dev_db/docker-compose.yaml`, following the
  shared-infrastructure pattern already used for Postgres (run once, used by all
  worktrees).
- Ports: `1025` (SMTP) and `8025` (web inbox) — Mailpit defaults.
- Mailpit starts automatically with the development environment as part of the
  `dev_db` composition.
- No persistent volume; captured mail is ephemeral.
