# Dev email viewer — django-mail-viewer

## Goal

Give developers and demo presenters an in-browser inbox to read the emails the
application sends during development, without sending real email and without
running any service outside Django.

## Approach

Use the third-party package `django-mail-viewer`. It provides a Django email
backend that captures outgoing email, plus a set of views (list + detail) that
render captured messages — including the HTML body — in the browser.

## Scope

- Add `django-mail-viewer` as a dependency.
- Add `django_mail_viewer` to `INSTALLED_APPS` for development only.
- Set the development `EMAIL_BACKEND` to the package's backend.
- Include the package's URLs under a development-only URL prefix.
- Document how to open the inbox during a demo.

## Out of scope

- Any change to production email sending.
- Persisting captured email across server restarts (unless the package's
  file-backed storage is chosen during implementation).

## Acceptance criteria

- Triggering an email-sending flow in development results in a message that is
  visible in the in-browser inbox.
- The HTML version of an email renders correctly in the viewer.
- No external process or binary needs to be started to view emails.
- Production email behaviour is unchanged.

## Open questions

- Which storage backend to use (in-memory vs file-backed) and whether captured
  email should survive a server restart.
- Whether the inbox URL should be reachable by any logged-in user in
  development or restricted further.
