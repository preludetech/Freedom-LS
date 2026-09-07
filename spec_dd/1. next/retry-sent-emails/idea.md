# Idea: retry sent emails

Outgoing mail now goes onto the task queue. Emails can fail to send, and that failure is silent to
the person waiting for the mail. Two questions, both answered before this idea was written:

**Does a failed send reach Sentry?** Yes, for a send that raises. `send_serialised_email` lets the
exception propagate, `django_tasks_db`'s worker marks the task result FAILED and re-sends
`task_finished` from inside its own `except` block, and `django_tasks.signals.log_task_finished`
calls `logger.exception(...)` there. The SMTP traceback is live, the record is ERROR, and
Sentry's default `LoggingIntegration` turns it into an issue. `init_sentry()` runs from
`DeploymentAppConfig.ready()`, so the worker process is instrumented too. A worker that is not
running at all, and a worker killed mid-send, are both caught separately by
`fls_run_housekeeping`'s existing sweeps.

Three gaps stay silent: `send_serialised_email` throws away the return value of
`connection.send_messages()`, so a backend that returns 0 without raising is recorded as a success;
the enqueue joins whatever transaction is open, so a rollback discards the mail with no trace; and
nothing sees what happens after the provider says 250 OK.

**Is there a retry?** No, and there is nothing upstream to switch on. `django-tasks` and
`django-tasks-db` are pinned at 0.12.0 and neither re-runs a FAILED result. `TaskContext.attempts`
exists but nothing increments it into a second run, and the `retry()` helper in
`django_tasks_db/utils.py` is database-write backoff, not task retry. `DBTaskResult` does carry
`run_after`, so delayed re-enqueue is available to build on.

So build the retry. Email is going to be used for a lot more than authentication. Learners could be
mailed about their progress, educators could be communicated with, and whatever is built has to
serve all of that rather than allauth alone. That points at the transport layer. `QueuedEmailBackend`
is already `EMAIL_BACKEND`, so every sender in the project, present and future, goes through it
without knowing.

Constraints settled with the user:

- **A persisted outbox row per message**, not an attempt counter riding in the task payload. It
  survives a lost task, it answers "did this person get their mail", and it stops the reset link
  being copied into a fresh task row on every attempt.
- **The payload is blanked as soon as the message is sent.** The row survives as the operational
  record; the body, which is where the reset link lives, does not.
- **Retries are re-driven automatically**, by a scheduled task and by a housekeeping sweep behind
  it. `WebhookDelivery.next_retry_at` is set today and nothing but an admin click ever reads it;
  that is the mistake to not repeat. An admin with a resend action is wanted as well, not instead.
- **One retry policy for all mail** for now. Per-category policies, priorities and a bulk queue wait
  for the first email type that needs them.
