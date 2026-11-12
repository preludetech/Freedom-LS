---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - EMAIL_BACKEND                            # optional: FLS now recommends QueuedEmailBackend; your settings keep whatever they set
  - EMAIL_MAX_ATTEMPTS                       # optional: default 6; freedom_ls_mail.E002 rejects a value below 1
  - EMAIL_RETRY_DELAYS                       # optional: default [60, 300, 900, 1800, 3600]; freedom_ls_mail.E002 rejects an empty list or a negative entry
  - EMAIL_RETRY_JITTER_RATIO                 # optional: default 0.2; freedom_ls_mail.E002 rejects a negative value
  - EMAIL_OUTBOUND_RETENTION_DAYS            # optional: default 30
  - EMAIL_FAILED_PAYLOAD_RETENTION_DAYS      # optional: default 3
  - HOUSEKEEPING_DUE_EMAIL_GRACE_SECONDS     # optional: default 300
  - HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE    # optional: default 500
  - HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS # hard under --deploy: freedom_ls_deployment.E008 enforces it against the worker settings
  - HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS   # hard under --deploy: freedom_ls_deployment.E008 now checks it against the worker settings too
  - HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS # hard under --deploy: freedom_ls_deployment.E008 now checks it against the worker settings too
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: retry sent emails

`QueuedEmailBackend` now records every outgoing message as an `OutboundEmail` row and retries a
send the mail host refused for a temporary reason. A permanent refusal or the last failed retry is
reported to Sentry, and a superuser can resend it from the Django admin. FLS's own production
settings now queue mail by default. Your project's settings are your own, so nothing about which
backend you use changes until you change it.

## Breaking changes

### Drain the email queue before deploying, if you already queue mail

This only matters if your `EMAIL_BACKEND` is already `freedom_ls.mail.backends.QueuedEmailBackend`.
The queued task, `freedom_ls.mail.tasks._send_email_task`, used to carry the whole serialised
message. It now carries only the id of an `OutboundEmail` row. A task enqueued by the old code and
picked up by the new worker fails, and that message is not sent. Let the worker empty the queue of
email tasks, then deploy. Mail sent while the old code is still running is what is at risk.

### The queue now needs `fls_run_housekeeping` as well as the worker

Each retry is enqueued to run after a backoff delay. `fls_run_housekeeping` enqueues again any row
that is past due, and re-sends any row a dead worker left in `sending`. Without housekeeping, a
retry whose task was lost is never made. Run it at least hourly wherever the queue is in use.

## Manual steps

1. **Run `python manage.py migrate`.** It adds `freedom_ls_mail.0001_initial`, the
   `OutboundEmail` table. With the queue selected and this migration missing, every send fails.

2. **Decide whether to queue outgoing email.** Retries happen only through the queue. To turn it
   on, run `python manage.py fls_run_worker` and schedule `fls_run_housekeeping`, then set:

   ```python
   EMAIL_BACKEND = "freedom_ls.mail.backends.QueuedEmailBackend"
   EMAIL_UPSTREAM_BACKEND = "django.core.mail.backends.smtp.EmailBackend"  # or your provider's
   ```

   A deployment that runs no worker keeps
   `EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"` and sends inside the request,
   with no retries. Queued mail with no worker behind it is accepted and never sent.

3. **Schedule `fls_run_housekeeping` at least hourly** if you queue mail. It also deletes
   finished `OutboundEmail` rows `EMAIL_OUTBOUND_RETENTION_DAYS` (30) after their last attempt, and drops the stored
   body of a failed row `EMAIL_FAILED_PAYLOAD_RETENTION_DAYS` (3) after its last attempt. A sent
   row's body is dropped as soon as it is delivered.

4. **Run `python manage.py check`, then `python manage.py check --deploy`.** The plain check runs
   **`freedom_ls_mail.E002`** (error): `EMAIL_RETRY_DELAYS` is empty or holds a negative or
   non-integer entry, `EMAIL_MAX_ATTEMPTS` is below 1, or `EMAIL_RETRY_JITTER_RATIO` is negative.
   Two new checks run under `--deploy`:
   - **`freedom_ls_deployment.E008`** (error, one per window): `HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS`,
     `HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS` or `HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS`
     is below `WORKER_MAX_TASK_SECONDS` plus `WORKER_HEARTBEAT_MAX_AGE_SECONDS` plus the worker's
     30-second watchdog poll. Housekeeping would then re-send a message, or close a task or report as
     failed, while its worker is still on it. The defaults (3600 against 1800 + 300 + 30) pass. If
     you have raised `WORKER_MAX_TASK_SECONDS`, raise all three windows with it. The two orphaned
     windows are not new, but a value below the ceiling that passed before now fails this check.
   - **`freedom_ls_mail.W001`** (warning): the queue is selected but the task backend cannot defer a
     task, so each retry waits for the next housekeeping run instead of its backoff delay. Use the
     database task backend.

5. **Tune the retry settings only if you need to.** All of them live in `freedom_ls/mail/config.py`
   with working defaults: `EMAIL_MAX_ATTEMPTS`, `EMAIL_RETRY_DELAYS`, `EMAIL_RETRY_JITTER_RATIO`,
   `EMAIL_OUTBOUND_RETENTION_DAYS`, `EMAIL_FAILED_PAYLOAD_RETENTION_DAYS`,
   `HOUSEKEEPING_DUE_EMAIL_GRACE_SECONDS`, `HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE` and
   `HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS`. Keep the whole `EMAIL_RETRY_DELAYS` ladder well
   inside the window after which housekeeping prunes finished task results.

The new admin screen for `OutboundEmail` is visible to superusers only. Queued messages now carry a
`Message-ID` header fixed when the message is first queued, so a duplicate delivery after a retry
can be collapsed by the mail client. A caller-supplied `Message-ID` is kept. The minted header goes
on the queued copy, never on your `EmailMessage`, so reusing one message object for several sends
gives each its own `Message-ID`.

With the inline task backend that dev and tests use, a send made inside `transaction.atomic()` is now
attempted straight away rather than at commit, so a failure raises `QueuedEmailNotSentError` to the
caller. A durable task backend still enqueues at commit.

No template review, package upgrade, `npm install` or Tailwind rebuild.
