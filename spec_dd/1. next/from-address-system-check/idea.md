# System check for a blank from-address when mail really delivers

## What

Add a Django system check to `mail` that warns when the configured email backend actually delivers
messages but `DEFAULT_FROM_EMAIL` is blank. Every FLS install that sends mail would be told at
`manage.py check` or `runserver` rather than after a relay rejects the first message.

## Why

`DEFAULT_FROM_EMAIL` falls back to `EMAIL_HOST_USER`, which defaults to an empty string. Both can be
empty, and Django will then build every message with an empty From address that most relays reject.
The `mail` app already has checks for its queueing backend and retry settings, but none for the
address mail is sent from. Every deployed install sends mail, so every concrete project would want
the same check.

## Settled

- Joins `mail`'s existing checks module, using the same `freedom_ls_mail.W...` id convention.
- A Warning, not an Error: the application still runs, and a project that intends a blank value can
  silence it.
- Quiet for backends that never put a message on the wire (console, in-memory, dummy), so dev
  consoles and the test suite stay clean.
- A whitespace-only address counts as blank.
- Only the from-address check is general. The reference's second check, about its own notification
  recipient list, is project-specific and stays in the project.

## Reference implementation

Concrete project at `/home/sheena/workspace/first_class/First-Class-LMS.git/main`:

- `apps/lead_forms/checks.py` (`check_from_address_set_when_email_delivers`, id W002, and the
  `_email_delivers` helper)
- `apps/lead_forms/tests/test_checks.py`

After the pull-in the project drops the from-address check but keeps its recipient check, and reuses
FLS's "does this backend deliver" helper for it.

## What becomes configurable

Nothing new. It reads `EMAIL_BACKEND` and `DEFAULT_FROM_EMAIL`, and is silenced through Django's
`SILENCED_SYSTEM_CHECKS`.

## Size

Small.

## Open questions

- When `EMAIL_BACKEND` is the FLS queueing backend, whether "delivers" should follow through to
  `EMAIL_UPSTREAM_BACKEND` (the backend the worker really sends with). The reference does not, since
  it has no queue. Following it is more accurate, and a spec should decide.
- Whether the check should run only under `--deploy`, or everywhere as the reference does.
- Whether a "delivers" helper should be exposed for other apps' checks.
