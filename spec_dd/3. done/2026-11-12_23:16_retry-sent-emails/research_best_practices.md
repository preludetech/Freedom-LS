# Research: best practices for a persisted email outbox with retry

Topic: `best_practices`. Sources are from established documentation and engineering writing. They were
cited from prior knowledge and not re-fetched in this session, so check the URLs before quoting them in the spec.

## 1. Transactional outbox

- The pattern: write the message as a row in the same database transaction as the business change.
  A separate relay then delivers it. This avoids the dual-write problem, where the DB commits but the
  send is lost, or the send happens and the DB rolls back. Delivery is at-least-once, so consumers or
  senders must tolerate duplicates. (https://microservices.io/patterns/data/transactional-outbox.html)
- Fit for FLS: the "row + task enqueued on commit" decision matches the pattern. In Django, the
  outbox row can be written inside the transaction and the task enqueued via `transaction.on_commit`.
  This is the documented way to tie side effects to commit (https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit).
- Caveat that follows from this: `on_commit` is itself a small dual-write. A crash between commit and
  enqueue loses the task, but not the row. So the sweep must also pick up rows that are `pending`
  with no live task. The row is the source of truth, and the task is only a trigger.
  Writing the row inside the transaction, with only the enqueue deferred, gives this property.
  Under `ATOMIC_REQUESTS` or tests, `on_commit` callbacks do not run in a non-committing `TestCase`
  unless `captureOnCommitCallbacks` is used (https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TestCase.captureOnCommitCallbacks).
- A rolled-back transaction discards the outbox row too (the user's chosen behavior). This is the
  intended pattern semantics. Call this out because it means no audit trail exists for such mail.
- Django-side prior art for a DB-backed mail queue: django-post_office (status, `scheduled_time`,
  `max_retries`, retry delay, a log of attempts) and django-mailer (deferred status, retry-deferred
  command). Both keep a row per message with a status and a retry loop, which supports the design here.
  (https://github.com/ui/django-post_office, https://github.com/pinax/django-mailer)

## 2. Classifying SMTP failures

Basis: RFC 5321 section 4.2 reply codes (https://www.rfc-editor.org/rfc/rfc5321#section-4.2).
- 2yz success. 4yz is "transient negative completion": the command was not accepted and the sender
  should retry later. 5yz is "permanent negative completion": do not repeat the same request.
  RFC 5321 section 4.5.4.1 says senders should retry on 4yz with a minimum interval of 30 minutes, and
  give up after at least 4-5 days. That is MTA-to-MTA queue guidance. An app submitting to a relay
  or provider (the case here) does not need those windows, because the provider is the MTA doing the
  long retry. The app's retry is for the submission hop (provider briefly unreachable, throttled).
- Enhanced status codes (RFC 3463, https://www.rfc-editor.org/rfc/rfc3463) 4.x.x vs 5.x.x agree with the first digit.
- Python `smtplib` exceptions (https://docs.python.org/3/library/smtplib.html#smtplib.SMTPException):
  - `SMTPException` is the base class, and a subclass of `OSError`.
  - `SMTPServerDisconnected`, `ConnectionError` and `socket.timeout` / `TimeoutError`, `OSError`
    (DNS failure, refused connection, network unreachable): transient.
  - `SMTPResponseException` has `smtp_code` and `smtp_error`. Classify by code: 4xx transient, 5xx
    permanent. Includes `SMTPSenderRefused`, `SMTPDataError`, `SMTPHeloError`.
  - `SMTPConnectError`: generally transient, as the connection failed (its code may be 4xx or 5xx, so
    decide by code, falling back to transient).
  - `SMTPAuthenticationError` (535): technically 5xx, but it is a configuration fault, not a
    per-message one. Retrying will not help until an operator fixes credentials. Treat as non-retryable
    for the message but alert loudly. Some teams prefer to keep these retryable, so that mail flows
    once the credential is fixed, because the whole stream is failing. This is a design decision for the spec.
  - `SMTPRecipientsRefused`: `.recipients` is a dict `{addr: (code, msg)}`. smtplib raises it only
    when all recipients are refused. A partial refusal does not raise and `sendmail()` returns the
    dict of refused ones. So classify per recipient: a 5xx (e.g. 550 mailbox does not exist) is a
    permanent failure for that address. A 4xx (450 greylist, 452 mailbox full) is transient.
    Mixed codes: retry if any is 4xx.
  - `SMTPNotSupportedError`, `SMTPHeloError`: config-class, not per-message.
- Django's SMTP backend (https://docs.djangoproject.com/en/stable/topics/email/#smtp-backend) calls
  `sendmail`, and swallows exceptions only when `fail_silently=True`. Note `send_messages` returns the
  number of messages sent. Django's `EmailMessage.send()` returns 0 when there are no recipients. A return of
  0 with no raise is neither success nor retryable: the idea already flags it as a silent gap. Treat as
  a distinct terminal state (e.g. failed/no-recipients), not "sent".
- Partial failure with multiple recipients: a single message to many recipients where some are refused
  and some accepted. A naive retry of the whole message re-sends to accepted recipients (duplicates).
  Best practice: either one outbox row per recipient (simplest, gives per-person "did they get it"),
  or narrow the recipient list on retry to the still-pending ones. The idea says the row answers "did this
  person get their mail", which points to one row per recipient.
- Default for unknown exceptions: treat as transient up to the retry cap, then dead-letter. Fail toward
  retry rather than silently drop, since the cap bounds the cost.
- Provider guidance on 4xx/throttling and retry (SES, Postmark, SendGrid docs) says: retry on throttling
  and 4xx/5xx-server-side with backoff, never retry on invalid-recipient or suppression errors.
  (SES: https://docs.aws.amazon.com/ses/latest/dg/send-email-concepts-process.html is the general
  reference; for error-retry guidance see https://docs.aws.amazon.com/general/latest/gr/api-retries.html.)

## 3. Backoff, jitter, retry windows

- Exponential backoff with jitter is the standard. Full jitter (`sleep = random(0, min(cap, base*2^n))`)
  or equal jitter spreads retries and avoids thundering herds after a provider outage
  (https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/).
- Transactional and auth email (password reset, email verification, login code) is time-sensitive:
  the user is waiting, and codes often expire in minutes to hours. So the ladder should be front-loaded
  (fast first retries: roughly 30s, 2min, 10min, then 30min, 1h) and capped, not stretch to days.
  The chosen "about 2 hours, 6 attempts" fits. Example ladder: +1m, +5m, +15m, +30m, +1h (sums to ~1h51m)
  with +/-20 percent jitter. Align the window with the shortest token lifetime (Django's
  `PASSWORD_RESET_TIMEOUT` defaults to 3 days, allauth login codes are much shorter, around 3 minutes by default
  for login-by-code, so retries after ~15 min may be useless for those).
  Consider noting that for short-lived codes a stale retry delivers an expired link and a confusing email.
- Store `next_attempt_at` (indexed) and `attempts` on the row. The scheduler selects `status=pending AND
  next_attempt_at <= now`. This is what `WebhookDelivery.next_retry_at` lacks: a reader.
- Honour provider `Retry-After`/throttle hints when available. For SMTP there is none, so a 421/451
  just uses the ladder.
- Cap total attempts and total age. Whichever hits first sends the row to the dead state.

## 4. Idempotency and duplicate avoidance

- Delivery is at-least-once. Exactly-once cannot be guaranteed, because a crash after the provider's 250
  and before the DB write marking `sent` makes a duplicate on retry. Minimise the window and accept it
  (https://brandur.org/idempotency-keys discusses the staged-atomic-phases approach; for email, the
  accepted trade is a rare duplicate over a lost mail).
- Claim/lease: take the row with an atomic conditional update or `select_for_update(skip_locked=True)`
  (Django: https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-for-update; PostgreSQL SKIP LOCKED
  is the standard queue-claim idiom, https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE).
  Flow: in a short transaction set `status=sending`, `claimed_at=now` (or `lease_expires_at`), commit; send
  outside any DB transaction (do not hold a lock during network I/O); then record the outcome.
  A conditional `UPDATE ... WHERE id=? AND status IN (pending) ` returning rowcount 1 is a simple claim
  that does not need long locks.
- Stuck `sending`: a worker killed mid-send leaves `sending` forever. The sweep re-drives rows whose
  lease expired (e.g. `sending` and `claimed_at` older than a few times the SMTP timeout). Set the lease
  well beyond the SMTP socket timeout so a slow live send is not stolen. Re-driving a stuck `sending`
  row risks a duplicate (the first attempt may have been accepted). Document that as the accepted trade.
  Count the stuck re-drive as an attempt, so a poison message cannot crash workers forever.
- Make the task idempotent on the row: the task carries only the outbox row id, and starts by loading
  the row and exiting if status is already `sent`/`dead`/cancelled. Duplicate tasks (on_commit double
  fire, sweep plus scheduler overlap) then become harmless.
- Set a stable `Message-ID` header once, when the row is created, and reuse it on each retry. Receiving
  MTAs and mail clients can dedupe on it, and it correlates logs. (RFC 5322 section 3.6.4,
  https://www.rfc-editor.org/rfc/rfc5322#section-3.6.4.) Some providers also accept an idempotency or
  custom header. SMTP itself has no idempotency key.
- Do not retry after a post-DATA ambiguous failure blindly: a timeout after DATA may or may not have
  delivered. For transactional mail the standard choice is to retry anyway (a rare duplicate beats a missing reset).

## 5. Dead-letter handling

- After the attempt or age cap, or on a permanent error, move the row to a terminal `dead`/`failed`
  status and stop automatic retries. Keep `last_error` (code and truncated message), `attempts`, and
  timestamps. Dead rows are queryable and visible in admin, and a resend action resets
  `status=pending, attempts=0` (or logs a new attempt) and re-enqueues. (DLQ concept:
  https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html.)
- Distinguish terminal states: `sent`, `failed_permanent` (5xx, bad recipient), `dead` (retries exhausted),
  `cancelled`. Admin resend of a permanent failure with a bad address is pointless unless the address
  is edited, so show the reason.
- Admin resend needs the payload. If the payload was scrubbed on a `sent` row, resend is impossible
  by design. Resend is for unsent rows only, which retain their payload. This is consistent with the idea.
  Dead rows keep their body, so their retention window matters (section 6).
- Keep a per-attempt log (small child table or JSON list of {time, outcome, code}) if debugging
  matters. At minimum keep `last_error`. Do not put recipient bodies in it.

## 6. PII and secrets in stored email

- Treat the body as sensitive: reset and verification links are bearer credentials. OWASP
  guidance: reset tokens should be single-use, short-lived, and not stored unnecessarily
  (https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html;
  https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html says not to log secrets/tokens).
- Scrub on success: null or empty the serialised body, subject, headers and attachments in the same
  `UPDATE` that sets `status=sent`. Keep metadata only: recipient, template/category, timestamps,
  attempts, Message-ID, status. Recipient address is itself PII, so the metadata row needs a retention
  policy too (GDPR/POPIA storage-limitation principle; the project operator is likely in scope of POPIA/GDPR).
- Unsent payload lives for the retry window (hours) and for dead rows until the admin acts. Set a
  retention for dead rows (e.g. 7 to 30 days), after which the housekeeping sweep also scrubs the payload,
  and a longer one (e.g. 90 days) after which it deletes the row. The sweep is the place for this.
- Where the body also appears elsewhere, scrub there too: the `django-tasks` task row (the idea already
  routes the id only, not the payload, so make sure the task args do not carry the message), Sentry
  events (`logger.exception` with a traceback can include local vars if `include_local_variables` is
  on, and SMTP error strings can echo the recipient; consider scrubbing), and application logs.
- Do not log message bodies or full links, even at debug. Log row id, Message-ID, outcome and code.
- Encryption at rest of the payload column is optional hardening (a Fernet field, key from env), and it
  is only worth it if DB backups or read replicas are a concern. Flag as optional, not required, given scrubbing.
- Admin: do not display the body of unsent rows to staff by default, or make it a deliberate action.
  Staff otherwise gain a way to read other users' reset links, i.e. account takeover. At least mark the
  body as read-only and restrict to superusers. This is a real risk worth a spec decision.
- Django admin note: the outbox model should be `has_add_permission = False` and mostly read-only.

## 7. Observability

- Alert on states, not only on exceptions: count of `dead` rows (any new dead row for auth mail is
  actionable), age of the oldest `pending` row (queue lag), count of `sending` past lease (worker
  crashes), and retry rate/ratio of sent-first-try vs retried. These are queue-health signals the
  Google SRE book calls out as symptom-based alerts (https://sre.google/sre-book/monitoring-distributed-systems/).
- Sentry: a transient failure that will be retried should not create a noisy issue per attempt. Log
  retryable failures at WARNING (or capture once with grouping), and ERROR/`capture_message` only on
  the transition to dead. This avoids six Sentry events per outage message. The idea notes the current
  worker FAILED path already goes to Sentry via `logger.exception`. If the task now catches and
  reschedules instead of raising, that path goes quiet, so the dead transition must report explicitly.
- Housekeeping check (`fls_run_housekeeping`): the sweep should also report counts (re-driven, scrubbed,
  dead) in its output, and raise or log at ERROR if dead rows exist above a threshold.
- Make the zero-return and enqueue-rollback gaps visible: `send_messages` returning fewer than expected
  should set a distinct status with a logged error.
- Provider-side delivery (bounces, complaints) is out of scope per the answers, so say clearly that
  `sent` means "accepted by the relay", not "delivered".

## 8. Summary recommendations for the spec

1. Outbox row per recipient message; the task carries only the row id; the row is the source of truth.
2. Write the row in the caller's transaction; enqueue on commit; a sweep rescues pending rows with no task.
3. Statuses: pending, sending (with lease), sent (payload scrubbed), failed_permanent, dead, cancelled.
4. Classify: 4xx / connection / timeout / OSError / unknown = retry; 5xx / all-recipients-refused with 5xx
   = permanent; per-recipient classification for refusals; auth/config errors = decide and alert.
5. Ladder of about 6 attempts over about 2h with full or equal jitter and a stored `next_attempt_at`.
6. Claim with a conditional update (or `skip_locked`), send outside a transaction, lease timeout much
   greater than the SMTP timeout, stuck rows count as an attempt. Accept rare duplicates; fix the Message-ID.
7. Scrub on send; retention for dead rows and metadata; restrict admin view of bodies.
8. Alert on dead rows, old pending rows and stuck sending rows; do not emit an ERROR per transient attempt.

## Open points for the spec to settle

- Per-recipient rows versus one row per message with narrowed recipients on retry.
- Whether authentication failures (535) are retried or dead-lettered immediately.
- Whether short-lived codes (login by code) should have a shorter cutoff than the global ladder.
- Dead-row and metadata retention periods.
- Who can read stored bodies in admin.

status: ok
