# Spec: retry sent emails

## Purpose

Outgoing mail leaves the request on the task queue (`freedom_ls/mail/backends.py`) and nothing
retries it. `django-tasks` and `django-tasks-db` are pinned at 0.12.0 and neither re-runs a FAILED
task result, so a mail host unreachable for thirty seconds costs the message permanently.

The failure is recorded. The worker marks the result FAILED, `django_tasks.signals.log_task_finished`
logs it at ERROR with the traceback, and Sentry's default logging integration raises an issue from
that record. But an issue in Sentry is not a delivered password reset, and under
`ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (`config/settings_base.py:404`) a lost verification mail
blocks registration outright.

Auth mail is all FLS sends today. Progress mail to learners and messages to educators are coming, so
the retry belongs at the transport layer, in the backend and the task that every
`EmailMessage.send()` already resolves through. A future sender then inherits it without a line of
its own. `idea.md` records what was checked and what the user settled.

## Terminology

| Term | Status | Meaning / source |
| --- | --- | --- |
| `OutboundEmail` | coined | The row that owns one outgoing message: its payload until it is sent, then its status, its attempts and its next attempt time. |
| the outbox table | narrowed | Prose for `OutboundEmail` rows. `django.core.mail.outbox` is the test-time list of sent messages and is a different thing, so write "the outbox table" or the model name, never a bare "the outbox". |

## Scope

**In.** A persisted `OutboundEmail` row per outgoing message, written by `QueuedEmailBackend`. A send
task that classifies its failure and schedules its own next attempt. Two housekeeping sweeps that
re-drive due and stranded rows. A read-only admin with a resend action. Payload scrubbing and row
retention. The two silent-failure gaps in today's backend: a discarded send count, and an enqueue a
rollback can take with it.

**Out.** Per-category retry policies, priorities and a separate bulk queue. One policy covers every
message FLS sends today, and the extension point is a module constant a later spec can turn into a
lookup. Bounce and complaint feedback from the mail provider, which needs provider webhooks and
answers a different question. Suppression and unsubscribe lists. Re-driving
`WebhookDelivery.next_retry_at`, which has the same flaw and is named here only so this design does
not copy it. Any change to a call site: `freedom_ls/accounts/allauth_account_adapter.py:52` still
calls `msg.send()` and learns nothing.

## Decisions

- **The retry state is a row, not a counter in the task payload.** An attempt counter riding in
  `DBTaskResult.args_kwargs` would copy the reset link into a fresh task row on every attempt, each
  one living the 14 days `prune_db_task_results` allows. It would also vanish if the enqueue were
  rolled back, or if the worker died between claiming and re-enqueuing, and then nothing would be
  left to sweep, because the row holding the state is the row that disappeared.

- **The task carries the row id and nothing else.** `_send_email_task(email_id)`. One copy of the
  message exists, in a row whose retention this spec owns.

- **`OutboundEmail` is not a `SiteAwareModel`.** `SiteAwareModelBase.site` is non-null and
  `SiteAwareManager` filters on the thread-local request, and mail is sent from management commands
  and crons that have neither. `site` is a nullable FK to `django.contrib.sites.Site`, captured
  best-effort at enqueue for admin filtering only, which is the same allowance
  `freedom_ls/webhooks/events.py` makes when it passes `site_id` explicitly into background work.
  Keeping the model off `site_aware_models` also keeps `mail` off a new edge in
  `docs/app_structure.md`.

- **`OutboundEmail` is not a `TimestampedModel`.**
  `freedom_ls/contrib/conformance/tests/test_timestamped_models.py:22` holds delivery records out of
  the allowlist on purpose, because they carry domain-meaningful timestamps that a generic
  `created_at`/`updated_at` pair invites a reader to confuse. This one declares `created_at`,
  `last_attempt_at`, `sent_at` and `scrubbed_at`.

- **Every attempt is its own task.** A sleep-and-retry loop inside one task would hold the
  single-threaded worker for hours, run past `WORKER_MAX_TASK_SECONDS`, and be killed mid-flight by
  the watchdog. That kill is `os._exit`, so it skips the bookkeeping that would have recorded how far
  the send got.

- **Two independent drivers, one idempotent entry point.** A deferred task is precise but can be
  lost. A housekeeping sweep is coarse but cannot be. Running both is what makes an unattended retry
  certain, and the claim `UPDATE` in Requirement 4 makes running both safe.

- **The ladder is shorter than the webhooks one.** `RETRY_DELAYS`
  (`freedom_ls/webhooks/delivery.py:20`) ends at 12 hours because the consumer there is a machine. An
  allauth confirmation key and a Django password-reset token both expire in three days by default,
  and a person blocked on verification re-requests within minutes, so mail delivered half a day late
  is mostly mail nobody needs any more.

- **The backoff helper is written locally rather than imported from `webhooks`.**
  `calculate_next_retry` is eight lines, and importing it would point the dependency arrow from
  infrastructure into a product app.

## Requirements

### 1. `OutboundEmail`, in a new `freedom_ls/mail/models.py`

The mail app gains its first model, its first `migrations/` package, and
`default_auto_field = "django.db.models.BigAutoField"` on `MailAppConfig`
(`freedom_ls/mail/apps.py`), matching `freedom_ls/webhooks/apps.py:7`.

| Field | Type | Note |
| --- | --- | --- |
| `id` | `UUIDField(primary_key=True, default=uuid4)` | The task argument, so it has to be JSON-safe as `str`. |
| `site` | `FK(Site, null=True, on_delete=SET_NULL)` | Best-effort, for admin filtering. No manager filters on it. |
| `message_id` | `CharField(max_length=255, unique=True)` | The pinned RFC 5322 `Message-ID`. See Requirement 2. |
| `to_emails` | `JSONField(default=list)` | Survives scrubbing. |
| `subject` | `CharField(max_length=255)` | Survives scrubbing. |
| `payload` | `JSONField(default=dict)` | The `SerialisedMessage`. Emptied on success. |
| `status` | `CharField(db_index=True)` | `queued`, `sending`, `sent`, `retrying`, `dead_letter`, `failed_permanent`. |
| `attempt_count` | `PositiveIntegerField(default=0)` | Incremented by the claim, not by the send. |
| `next_attempt_at` | `DateTimeField(db_index=True)` | Non-null from creation, `timezone.now()` for a fresh row, so no sweep needs a null branch. |
| `last_attempt_at` | `DateTimeField(null=True)` | Written by the claim. The stuck-row sweep measures from it. |
| `last_error` | `TextField(blank=True, default="")` | Truncated to 1000 characters in `save()`, copying `WebhookDelivery.save()` (`freedom_ls/webhooks/models.py:422`). |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `sent_at` | `DateTimeField(null=True)` | |
| `scrubbed_at` | `DateTimeField(null=True)` | When the payload was emptied. |

Index `(status, next_attempt_at)`. Both sweeps and the claim read on that pair.

### 2. `QueuedEmailBackend` writes the row (`freedom_ls/mail/backends.py`)

`_queue_or_send` keeps its two existing early paths unchanged. A message with no recipients is still
declined, and an `UnserialisableMessageError` still falls back to `_send_now`. Say in the docstring
that the fallback bypasses the outbox table and so is never retried. Nothing in FLS reaches it.

Otherwise, in order:

1. **Pin the `Message-ID` before serialising.**
   `message.extra_headers.setdefault("Message-ID", make_msgid(domain=DNS_NAME))`, using
   `email.utils.make_msgid` and `django.core.mail.utils.DNS_NAME`, which is the pair
   `EmailMessage.message()` uses. Without this, Django mints a fresh id on every attempt and a
   duplicate arrives as a second message. With it pinned, a conformant client collapses the two.
2. **Create the row**, synchronously, inside whatever transaction the caller has open. A rollback
   takes the row with it and no mail is sent, which is the right outcome, because the account the
   verification link points at was not written either. `site` comes from `get_cached_site` via
   `freedom_ls.site_aware_models.models._thread_locals`, guarded so a request-less caller gets
   `None`.
3. **Enqueue on commit.** `transaction.on_commit(...)` wrapping
   `default_task_backend.enqueue(_send_email_task, args=[str(email.pk)], kwargs={})`. Outside an
   atomic block `on_commit` runs immediately, so the un-transactioned path, which is all of FLS
   today, is unchanged. An exception inside the callback is captured to Sentry and swallowed. The row
   is already durable, the sweep in Requirement 5 picks it up, and raising after the commit reaches
   no caller that could act on it.

A `DatabaseError` from the row insert keeps today's handling. It is re-raised unless `fail_silently`,
and today's comment about not falling back to an inline send still applies.

`EMAIL_TASK_PRIORITY = 10` is unchanged, and applies to retries as well as first attempts.

### 3. Error classification, in a new `freedom_ls/mail/errors.py`

One function, `classify(exc: BaseException) -> Literal["transient", "permanent"] | None`, returning
`None` for an exception that is not a send failure at all.

**Transient.** `SMTPServerDisconnected`, `SMTPConnectError` and `SMTPHeloError`. Any
`SMTPResponseError` subclass whose `smtp_code` is 4xx, which is 421, 450, 451 and 452, all "try
later" by RFC 5321; reading `getattr(exc, "smtp_code", None)` covers `SMTPSenderRefused` and
`SMTPDataError` in the same branch. `SMTPRecipientsRefused` where every code in `exc.recipients` is
4xx, which is what greylisting looks like. `TimeoutError`. `ConnectionRefusedError`,
`ConnectionResetError` and `BrokenPipeError`. `socket.gaierror`. `ssl.SSLError`. An otherwise
unmatched `OSError` or `SMTPException`. And `EmailNotSentError`, from Requirement 6.

**Permanent.** `SMTPAuthenticationError`, because retrying wrong credentials once per message across
a backlog is how a provider locks the sending account. `SMTPNotSupportedError`. Any
`SMTPResponseError` whose `smtp_code` is 5xx. `SMTPRecipientsRefused` with any 5xx code. `ValueError`,
which is what `SMTPBackend.prep_address` raises for a malformed address and what `BadHeaderError`
subclasses; a CR/LF injection is never worth retrying. `SSLCertVerificationError`, which is a deploy
fault rather than a blip. `UnicodeEncodeError`.

**Neither.** Anything else. A `KeyError` in FLS's own code is a bug, not a mail failure, and
Requirement 4 lets it propagate so the existing task-failure path reports it with its traceback.

Record in the module docstring the one case this cannot see. `smtplib.sendmail` raises
`SMTPRecipientsRefused` only when every recipient is refused, and Django's `_send` discards a partial
refusal, so a message accepted for some recipients is recorded as sent. Retrying it would duplicate
to the accepted ones, so it is left alone. FLS mail is single-recipient today.

### 4. The send task, in `freedom_ls/mail/tasks.py`

`_send_email_task(email_id: str)` delegates to `send_outbound_email(email_id)`, which:

1. **Claims the row atomically.**
   ```python
   claimed = OutboundEmail.objects.filter(
       pk=email_id, status__in=(QUEUED, RETRYING)
   ).update(
       status=SENDING,
       attempt_count=F("attempt_count") + 1,
       last_attempt_at=timezone.now(),
   )
   if not claimed:
       return
   ```
   That one `UPDATE` is the whole guard. Hand the same id to two workers and one gets `1` while the
   other gets `0` and returns. A row already `sent` matches nothing.
2. Rebuilds the message with `deserialise_message`, applies `set_8bit_encoding`, and sends through
   `EMAIL_UPSTREAM_BACKEND`, which is the body of today's `send_serialised_email` plus Requirement 6.
3. **On success**, in one `save`: `status=sent`, `sent_at`, `payload={}`, `scrubbed_at`,
   `last_error=""`. Nothing sits between the send and this write, no logging call and no Sentry
   flush, because that gap is the window in which a killed worker leaves a delivered message looking
   unsent.
4. **On a transient failure**, schedules the retry described in Requirement 5 and logs at WARNING. A
   greylisting pause is not an incident and must not page anyone.
5. **On a permanent failure**, sets `status=failed_permanent` and `last_error`, and reports one
   `sentry_sdk.capture_exception`.
6. **On anything `classify` returns `None` for**, re-raises. The row stays in `sending` and the sweep
   in Requirement 5 recovers it, while the task result goes FAILED and reports itself as it does
   today.

### 5. Scheduling and re-driving

**`freedom_ls/mail/retry.py`** holds two functions. `next_attempt_delay(attempt_count)`
walks the `config.EMAIL_RETRY_DELAYS` ladder, repeating the last value once past its end, and adds
`random.uniform(0, base * config.EMAIL_RETRY_JITTER_RATIO)`, shaped after `calculate_next_retry`
(`freedom_ls/webhooks/delivery.py:229`). `schedule_retry(email, exc)` does the rest:

- At or past `config.EMAIL_MAX_ATTEMPTS` the row goes to `dead_letter`, `next_attempt_at` is left
  where it is, and a `sentry_sdk.capture_message` records it with constant text and the row id,
  attempt count and status on the scope, so every dead letter groups into one recurring issue.
  `mark_orphaned_running_tasks_failed` (`freedom_ls/deployment/housekeeping.py:102`) is the pattern.
- Otherwise the row goes to `retrying` with `next_attempt_at = now + next_attempt_delay(...)` and
  `last_error` set, and the retry is enqueued deferred:

```python
if default_task_backend.supports_defer:
    _send_email_task.using(run_after=email.next_attempt_at).enqueue(str(email.pk))
```

That guard is load-bearing. `django_tasks_db.DatabaseBackend` sets `supports_defer = True` and
`DBTaskResultQuerySet.ready()` genuinely holds a deferred row back, but
`django.tasks.backends.immediate.ImmediateBackend` leaves it `False` and `Task.__post_init__` calls
`validate_task`, so `.using(run_after=...)` raises `InvalidTaskError` under the dev and test `TASKS`
(`config/settings_base.py:493`). Falling back to an undeferred enqueue there would be worse than
doing nothing, because under `ImmediateBackend` it would run the whole ladder inside the originating
request. Skipping leaves the row to housekeeping, which is a correct if coarser driver.

**Sweeps in `freedom_ls/deployment/housekeeping.py`**, each called from `run_housekeeping_sweeps()`
in its own `try`, in the established style. A `SWEEP_FAILURES` exception becomes a `sweep_failures`
entry, and what a sweep finds becomes a `findings` entry.

- `requeue_due_outbound_email()` re-enqueues rows in `queued` or `retrying` whose `next_attempt_at`
  passed more than `config.HOUSEKEEPING_DUE_EMAIL_GRACE_SECONDS` ago, ordered by `next_attempt_at`
  and capped at `config.HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE`, undeferred. The grace window stops
  the sweep racing a scheduled task that is about to fire anyway. This is what catches an enqueue
  that never happened, a task row deleted or lost, and a deployment whose backend cannot defer. It
  re-enqueues and never sends, so housekeeping stays fast and the sending stays with the worker.
- `recover_stuck_outbound_email()` takes rows in `sending` whose `last_attempt_at` is older than
  `config.HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS`. This is the worker-died-mid-send recovery. Below
  the attempt cap the row returns to `retrying` with `next_attempt_at = now`, and at the cap it is
  dead-lettered. Either way it records a `capture_message` in the constant-text shape above. Such a
  row is genuinely ambiguous, because the message may already have been delivered, and it is re-sent
  anyway: a lost verification mail blocks registration, while a duplicate is an annoyance.
- `prune_outbound_email()` deletes rows in a terminal status older than
  `config.EMAIL_OUTBOX_RETENTION_DAYS`, and empties `payload` on `failed_permanent` and `dead_letter`
  rows older than `config.EMAIL_FAILED_PAYLOAD_RETENTION_DAYS`, stamping `scrubbed_at`. The payload
  outlives the failure by that window so the admin resend has something to send. Scrubbing it at once
  would make the action useless.

Rows dead-lettered by a run are a `findings` entry, not a `sweep_failures` one. Housekeeping did its
job and is reporting something wrong elsewhere, which is the split `HousekeepingOutcome`
(`housekeeping.py:41`) already draws.

### 6. The discarded send count (`send_serialised_email`)

```python
sent = connection.send_messages([message])
if not sent:
    raise EmailNotSentError(
        f"{config.EMAIL_UPSTREAM_BACKEND} raised nothing and reported 0 messages sent."
    )
```

`SMTPBackend.send_messages` returns 0 without raising when `open()` failed quietly, and a provider's
API backend routinely returns 0 for a message it rejected. Today that marks the task successful with
nothing sent. `EmailNotSentError` is declared in `mail.py` beside `UnserialisableMessageError` and
classified transient. Pass `fail_silently=False` to `get_connection` explicitly. It is the default,
but this code exists so that failures are loud.

### 7. Admin, in a new `freedom_ls/mail/admin.py`

`unfold.admin.ModelAdmin`, not `SiteAwareModelAdmin`, because the model is not site-aware. Shaped
after `WebhookDeliveryAdmin` (`freedom_ls/webhooks/admin.py:201`): `list_display` of recipients,
subject, status, attempt count, last attempt and last error; `list_filter` on status and site;
`search_fields` on `message_id` and `to_emails`; add, change and delete permissions all `False`.

`payload` appears in no `list_display`, no `readonly_fields` and no detail view. An admin screen that
renders a live password-reset link is a worse leak than the row itself.

One action, resend, over rows in `failed_permanent`, `dead_letter` or `sending`. It resets
`attempt_count` to 0, sets `status=queued` and `next_attempt_at=now`, and enqueues. It must not send
inline the way `retry_deliveries` does, which would hold an admin request open for a whole SMTP
session. A row whose payload has already been scrubbed is skipped, with a `messages.warning` naming
it.

### 8. Settings, in `freedom_ls/mail/config.py`

Declared in `DeploymentSettings.declared_settings`, all with defaults, so no downstream environment
change is required:

| Setting | Default |
| --- | --- |
| `EMAIL_MAX_ATTEMPTS` | `7`, an initial send plus six retries |
| `EMAIL_RETRY_DELAYS` | `[60, 300, 900, 3600, 10800, 21600]` seconds |
| `EMAIL_RETRY_JITTER_RATIO` | `0.2` |
| `EMAIL_OUTBOX_RETENTION_DAYS` | `30` |
| `EMAIL_FAILED_PAYLOAD_RETENTION_DAYS` | `3` |
| `HOUSEKEEPING_DUE_EMAIL_GRACE_SECONDS` | `300` |
| `HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS` | `3600` |
| `HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE` | `500` |

`HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS` follows the ceiling rule the existing orphan windows
document (`config.py:56`): at or above `WORKER_MAX_TASK_SECONDS` plus
`WORKER_HEARTBEAT_MAX_AGE_SECONDS` plus one watchdog poll, so a send still legitimately in flight is
never recovered out from under the worker holding it.

Add `freedom_ls_mail.W001` to `freedom_ls/mail/checks.py`, warning when `EMAIL_BACKEND`
is `QueuedEmailBackend` but `default_task_backend.supports_defer` is `False`, because on that
configuration every retry waits for `fls_run_housekeeping`.

## Testing

Two existing patterns carry this. `freedom_ls/mail/tests/conftest.py` has `upstream_locmem`,
which points the backend behind the queue at locmem so `mail.outbox` is the record of what went out.
`test_housekeeping.py` has `database_task_backend` (`:50`), which swaps `TASKS` to the real database
backend. Tests that cross `on_commit` need `django_capture_on_commit_callbacks`, and the backend
tests gain `django_db` because they now write a row.

**The backend.** One row per message, and none for a message with no recipients. The task argument is
a UUID string and nothing else, which is the standing guard against the payload creeping back into
`DBTaskResult.args_kwargs`. The `Message-ID` is pinned on the row and present in the delivered
message. The enqueue happens on commit, and a rolled-back transaction leaves neither row nor task. An
enqueue that raises after the commit leaves the row queued and does not propagate.

**The send.** A success marks the row sent, empties the payload, and keeps recipients, subject and
`message_id`. A transient error schedules a retry with the expected delay, parametrised over
`SMTPServerDisconnected`, `SMTPConnectError`, `TimeoutError`, `ConnectionResetError`,
`socket.gaierror`, `SMTPDataError(451, ...)`, `SMTPSenderRefused(452, ...)` and
`SMTPRecipientsRefused({addr: (450, ...)})`. A permanent error is not retried, parametrised over
`SMTPRecipientsRefused({addr: (550, ...)})`, `SMTPSenderRefused(550, ...)`,
`SMTPAuthenticationError`, `SMTPNotSupportedError`, `BadHeaderError` and `SSLCertVerificationError`.
A backend that returns 0 without raising is a failure, not a success. An unexpected exception
propagates and leaves the task result failed. The attempt cap dead-letters the row and reports to
Sentry with no payload on the scope. A redelivered task does not send twice, and a row already sent
is not re-sent. Jitter never shortens the base delay.

**The drivers.** A retry is enqueued with a future `run_after` under the database backend, and no
retry task is enqueued at all when the backend cannot defer. A due row is requeued by housekeeping
with no admin intervention, which is the named guard against repeating the `WebhookDelivery` flaw. A
row not yet due, or due but inside the grace window, is left alone. A row stuck in `sending` past the
window returns to `retrying`, or dead-letters at the cap. The requeue sweep respects the batch size.
Sent rows past retention are deleted, and failed rows past the payload window are scrubbed. A
`DatabaseError` in an email sweep is a sweep failure, and a dead letter is a finding.

**Config**, in `test_config.py`, in the style of
`test_heartbeat_tick_is_well_inside_the_heartbeat_window` (`:36`). One assertion per new default,
plus the two relationships that matter. The whole ladder finishes inside the task-result prune
window, and the stuck-email window is at or above the true task ceiling.

## Documentation and downstream

- `docs/product/deployment.md:13` says today that a never-sent email "fails silently". It no longer
  does. `fls_run_housekeeping` also changes role there, from hygiene and reporting to the backstop
  that makes retries certain, so its recommended cadence of at least hourly belongs in the same
  paragraph.
- `docs/product/configuration-and-extension.md` gains the new settings.
- `docs/product/security-and-data-handling.md` gains what the outbox table stores, that a message
  body is discarded on delivery, and how long a row survives.
- `docs/app_structure.md` needs regenerating. `mail` gains no FLS edge, but it gains models.
- `upgrade_notes.md` for the branch: run `migrate` for the mail app's first migration, run
  housekeeping at the recommended cadence, and note that a deployment sending through Django's SMTP
  backend rather than the queue gets none of this and is otherwise unchanged.

## Open questions

- Thirty days for a row and three days for a failed payload are engineering guesses. Both are a
  retention call to check against `legal_docs/` before the first production deployment holds real
  learner mail.
- Whether a dead letter should escalate past a Sentry issue, to something like a daily digest of
  undelivered mail, once there are enough kinds of email for the volume to be worth reading.

## Success criteria

- A mail host refusing connections for ten minutes delivers the password reset once it returns, with
  no operator action and no second request from the learner.
- A row whose scheduled task never existed is picked up by the next `fls_run_housekeeping` run.
- A worker killed mid-send leaves a row that the next housekeeping run returns to `retrying`.
- A delivered message's row holds no body, no alternatives and no attachments.
- An SMTP 550 produces exactly one Sentry issue and no second attempt.
- `DBTaskResult.args_kwargs` for `_send_email_task` holds a UUID and nothing else.
- `freedom_ls/accounts/allauth_account_adapter.py` is unchanged, and a new sender gets retries by
  calling `send()`.
