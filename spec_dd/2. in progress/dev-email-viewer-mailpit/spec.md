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

- Provide a way to run Mailpit locally (binary or container) as part of the
  development setup.
- Configure the development `EMAIL_BACKEND` / SMTP settings to send to Mailpit's
  SMTP listener.
- Document how to start Mailpit and open its web inbox during a demo.

## Out of scope

- Any change to production email sending.
- Bundling or vendoring the Mailpit binary into the repository.

## Acceptance criteria

- With Mailpit running, triggering an email-sending flow in development results
  in a message that appears in the Mailpit web inbox.
- The HTML, plain-text, and raw views of an email are all viewable.
- Production email behaviour is unchanged.
- Starting Mailpit and reaching its inbox is documented and repeatable.

## Open questions

- How Mailpit is provided to developers (standalone binary vs container vs an
  addition to an existing compose setup).
- Which ports to use for Mailpit's SMTP and web interfaces.
- Whether Mailpit should start automatically with the development environment or
  be started manually.
