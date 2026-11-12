# Research: known complaints about queued email, retry and resend

Topic: `known_complaints`. Question: what do users commonly complain about with this kind of work?

Evidence quality: web search was shallow. Only a few primary sources were confirmed (marked CONFIRMED with a URL). Items marked UNSOURCED are well-known failure modes from general knowledge that the searches did not turn up a specific thread for; treat them as design checks, not as cited findings.

## 1. Duplicate emails

- CONFIRMED: django-mailer issue 160. A user running several app instances, each with cron enabled, got duplicate emails. The maintainer replied that locking should prevent duplicates. The issue was left open and unresolved (the reporter later tied it to their own feature sending one email per shared note). https://www.github.com/pinax/django-mailer/issues/160
- CONFIRMED (by search summary): django-mailer 2.0 added DB row-level locking on top of its file lock, because the file lock alone did not stop multiple sends of one message. A file lock does not work across hosts. https://pypi.org/project/django-mailer/2.0
- CONFIRMED (by search summary): a Mozilla Kitsune PR argues django-post-office's `send_queued` (query batch, send, then update status) with a file lock may overlap between runs and double-send. https://https-github_com.proxy.bugsmash.io/mozilla/kitsune/pull/6533
- CONFIRMED (by search summary): Celery tasks run twice after a worker crash with `acks_late`, or when a Redis visibility timeout is shorter than the task. The usual advice is an idempotency key or a recorded sent-state written atomically, since check-then-send itself races. https://github.com/celery/celery/issues/4426 and https://dev.to/polly_colson_e4498b3f8e1c/celery-retries-keep-duplicating-after-redis-visibility-timeout-490f
- Bearing on idea.md: HIGH. Several workers or a scheduled task plus a housekeeping sweep both re-drive the same row. The persisted outbox row needs an atomic claim (for example `select_for_update(skip_locked=True)` or a conditional status update from queued to sending) so the scheduled task, the sweep and an admin resend cannot all send one row. The window that cannot be closed is "provider accepted, worker died before recording success": the retry then duplicates. Decide and document that this is at-least-once delivery.

## 2. Emails stuck in queued/sending

- CONFIRMED: the django-post-office searches turned up no specific "stuck in sending" issue; the practical advice found was to check that only one `send_queued` runs and whether the lock file is cleaned up after crashes. A crash leaving a stale lock or a row in a sending state is the standard version of this. https://pypi.org/project/django-post-office
- UNSOURCED: a row marked "sending" by a worker that is killed never leaves that state unless something times it out.
- Bearing: HIGH. idea.md says a worker killed mid-send is caught by `fls_run_housekeeping`. The spec needs a lease/`sending_started_at` timeout that returns the row to retryable, and that interacts with section 1: the timeout must be longer than the longest legitimate send or it creates the duplicates it should prevent.

## 3. Stale password-reset and verification links arriving late

- UNSOURCED (no thread found): retrying for up to ~2 hours delivers a reset or verification link long after the user gave up and requested a second one, or after the link's token lifetime. Multiple links in the inbox, where an older one is invalidated by the newer one, is the common user confusion.
- Bearing: HIGH and specific to the chosen policy (about 2 hours, ~6 attempts, one policy for all mail). Consider a per-message expiry (do not send after N minutes) or at least checking the 2 hour ladder against the allauth/Django token lifetimes and login-code lifetimes. idea.md defers per-category policy; this is the likely first case that forces it. Admin resend of an authentication email after the token has expired also sends a dead link; the resend UI could warn.

## 4. Outbox tables growing without bound

- CONFIRMED: django-post-office ships `cleanup_mail`, deleting mail older than a number of days (default 90), and its README suggests cron. A 0.7.2 changelog entry notes making it more efficient with millions of rows. https://pypi.org/project/django-post-office/0.7.2 and https://pypi.org/project/django-post-office/0.8.4
- CONFIRMED: django-mailer ships `purge_mail_log` for the same reason (from its docs). https://github.com/spookylukey/django-mailer/blob/master/docs/usage.rst
- Bearing: MEDIUM. A persisted row per message for all mail (including future learner progress mail) grows steadily. Plan retention for sent and dead rows and run it from the same housekeeping sweep, with an index on the status and next-attempt columns the sweep filters on.

## 5. Sensitive content stored in outbox or logs

- UNSOURCED (no thread found): the default behaviour of these packages is to store full bodies indefinitely, which includes reset links, one-time codes and personal data. Exception messages and logged tracebacks can also include recipient addresses or message fragments.
- Bearing: HIGH, and idea.md already blanks the payload on success. Open points: dead rows keep their payload for the admin resend (so retention applies to them); the stored `last_error` text and the `logger.exception` output reach Sentry and may include recipient addresses or provider responses echoing content; admin list/detail views should not display bodies of authentication mail casually.

## 6. Retries hammering a rate-limited or failing provider

- CONFIRMED (by search summary): django-mailer added `MAILER_EMAIL_MAX_RETRIES`, defaulting to unlimited, after unlimited retry of deferred mail was a problem. https://pypi.org/project/django-mailer/2.1 and https://groups.google.com/g/django-mailer/c/glkmPZgmHmM
- CONFIRMED: Anymail's guidance on transient errors says to retry only transient failures, not permanent ones. https://anymail.dev/en/v9.2/tips/transient_errors/ (page was not fully read; redirect from the readthedocs URL)
- Bearing: HIGH. A bounded ladder (6 attempts, ~2 hours) is already in the answers. Still needed: classify permanent errors (auth failure, invalid recipient, 5xx permanent codes) so they go dead at once instead of waiting out the ladder; add jitter; respect `Retry-After` / 429 where available; and cap the batch size the sweep claims per run so a recovery after an outage does not burst-send everything at once.

## 7. Partial-recipient failures

- UNSOURCED for these packages: `send_messages` over SMTP can accept some recipients and reject others (smtplib `sendmail` returns a dict of refused recipients, and raises only if all are refused). A retry of the whole message then re-sends to the recipients who already received it.
- Related, already in idea.md: `send_serialised_email` discards the return value of `send_messages()`, so a 0 return counts as success.
- Bearing: MEDIUM. Decide whether the outbox row is per message or per recipient. With one row per message, either treat partial acceptance as success and record the refused addresses, or send one message per recipient. Treat a return of 0 as a failure to retry.

## 8. Admin resend going to a wrong or changed address

- UNSOURCED (no thread found): resend re-uses the stored recipient, but the user may have changed their email since (or the stored address was the old one for an email-change confirmation). Resending sends something the person no longer controls, or to an address now owned by someone else.
- Bearing: MEDIUM. Resend should use the snapshot stored on the row, show it to the admin before confirming, and record who resent and when. Because the payload is blanked on success, resend only works for non-sent rows; say so in the admin (an already-sent row has nothing to resend).

## 9. Tests and dev setups where mail silently does not send

- CONFIRMED (general Django behaviour): the test runner swaps `EMAIL_BACKEND` for the locmem backend, so tests that go through the queue backend never exercise it, and `mail.outbox` assertions pass or fail for the wrong reasons. Packages such as django-post-office document a `POST_OFFICE` `BACKENDS` setting so that the queued layer and the real layer can be configured separately. https://pypi.org/project/django-post-office
- UNSOURCED: in dev, with a queue backend and no worker running, mail is "sent" in the view but never leaves, which looks like a bug in the feature being developed.
- Bearing: MEDIUM. Add settings or a documented way for tests to run the task inline, and a dev note (or console backend plus a worker command) so that a missing worker is obvious. The housekeeping check for a not-running worker already exists per idea.md.

## 10. Enqueue inside a transaction

- CONFIRMED (general Django, `transaction.on_commit`): enqueueing inside an open transaction can run the task before commit (the worker finds no row), or after rollback (mail for something that never happened). The answers file chose to enqueue on commit. A known gotcha is that `on_commit` does not run inside a `TestCase` unless `captureOnCommitCallbacks` is used, so tests of the enqueue path silently see no task. https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit
- Bearing: MEDIUM. If the row is created inside the transaction but the task is enqueued on commit, a failure of the enqueue itself (broker/DB down) after commit leaves a queued row with no task; the housekeeping sweep for orphaned queued rows must cover this case, and it should be tested.

## Summary of items most affecting the design

1. Atomic claim and a lease timeout on "sending" (sections 1, 2).
2. Staleness policy for authentication mail under a 2 hour ladder (section 3).
3. Permanent versus transient error classification, jitter and sweep batch caps (section 6).
4. Return value of `send_messages` and the partial-recipient decision (section 7).
5. Retention of sent and dead rows, and what is kept in `last_error` (sections 4, 5).
6. Orphaned-queued-row sweep and test support for on_commit and inline execution (sections 9, 10).

status: ok · reason: web sources thin; several themes marked UNSOURCED
