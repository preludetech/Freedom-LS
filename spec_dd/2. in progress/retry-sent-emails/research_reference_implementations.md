# Research: reference implementations of queued mail with retry

Topic: `reference_implementations`. Question: how do other systems model and retry queued mail?

Provenance note: written from working knowledge of each project's documented design, not from a fresh
read of each repo at the current release. Behaviour details (defaults, field names) should be
re-verified against the linked docs before the spec cites them as fact.

## Summary table

| System | Outbox row | Retry trigger | Schedule | Double-send guard | Payload kept | Admin |
|---|---|---|---|---|---|---|
| django-post-office | `Email` + `Log` | cron `send_queued_mail` | `max_retries` + `retry_interval` | status flip + `select_for_update`-style batch claim | forever unless cleaned | list, resend-ish actions, log inlines |
| django-mailer | `Message`, `MessageLog`, `DontSendEntry` | cron `send_mail`, `retry_deferred` | manual/cron, no backoff | lock file / DB lock around run | log keeps message data | admin for all three |
| django-celery-email | none | Celery task retry | Celery `max_retries`, `default_retry_delay` | none (at-least-once) | none (in broker) | none |
| django-anymail | none (library) | none | none | `esp_name`, `message_id`, `status` returned | n/a | none (webhooks signal) |
| Rails ActiveJob | job in queue backend | `retry_on` | `wait: :polynomially_longer`, `attempts` | none (at-least-once) | job args in queue | queue UI (Sidekiq, GoodJob, Solid Queue) |
| Laravel queued mail | `failed_jobs` table | `$tries`, `$backoff`, `queue:retry` | per-attempt backoff array | none (at-least-once) | serialised in `failed_jobs` | `queue:retry` CLI, Horizon |
| Transactional outbox (Discourse, GitLab) | `*_events` / job row | poller | backoff + disable | idempotency key / row status | varies | admin UI |

## django-post-office

- Data model: `Email` (from, to, cc, bcc, subject, message, html_message, `status` in
  sent/failed/queued/requeued, `priority`, `scheduled_time`, `expires_at`, `number_of_retries`,
  `headers`, `context`, `backend_alias`, `template`) plus `Log` (email FK, date, `status`,
  `exception_type`, `message`) one row per attempt, plus `Attachment`, `EmailTemplate`.
- Trigger: a management command `send_queued_mail` run from cron every minute (or Celery beat). It
  selects `queued` (and `requeued` with `scheduled_time` due) mail. There is no in-process worker.
- Retry: `settings.POST_OFFICE['MAX_RETRIES']` and `RETRY_INTERVAL` (a `timedelta`). On failure,
  if `number_of_retries < max_retries` the email is set `requeued` with `scheduled_time = now +
  retry_interval`. Interval is fixed, not exponential. Final failure leaves `status=failed`.
- Double-send: batch claim by status; the sender marks mail inside a transaction. Concurrent
  `send_queued_mail` runs historically could race (reported duplicate sends); a lock was added
  (`--lockfile`, and later DB-level locking). Lesson: claim rows atomically before sending.
- Storage: everything stays forever. `cleanup_mail --days=90` deletes old mail (and attachments),
  `--delete-attachments`. Without scheduling cleanup, the table, and the bodies with it, grows
  unbounded and holds plaintext bodies indefinitely.
- Admin: strong. Email list with status filter, `Log` inline, "Requeue failed emails" bulk action,
  preview of body. Resend is just flipping status back to queued.
- Where it went wrong: retained bodies forever (privacy: reset links, tokens at rest); fixed-interval
  retry with no jitter; cron dependency means retries are only as live as the cron; a race between
  overlapping senders. No payload scrubbing.

## django-mailer

- Data model: `Message` (queued: `email` pickled/serialised blob, `priority`, `when_added`),
  `MessageLog` (sent or failed archive: `message_data`, `result` success/failure/do-not-send,
  `log_message`), `DontSendEntry` (address blocklist), plus `Message.deferred` timestamp.
- Trigger: `send_mail` management command from cron; `retry_deferred` command sets `deferred=None`
  on deferred messages so they are tried again. Deferral happens on a send failure (the message is
  marked deferred and skipped by later runs).
- Schedule: none automatic. Deferred mail stays deferred until a human or a cron runs
  `retry_deferred`. This is the same class of mistake as `WebhookDelivery.next_retry_at`: state
  recorded, nobody re-drives it. Newer versions added `MAILER_EMPTY_QUEUE_SLEEP` and
  `runmailer` loops, but deferral is still not auto-retried by default.
- Double-send: file lock (`mailer.lock`) around `send_all`, and later a DB lock; per-message
  `deferred` flag. Lock-file approach breaks across hosts.
- Storage: successful messages move to `MessageLog` (`MAILER_LOG_...` settings); `purge_mail_log
  <days>` command deletes old logs. Log retains full message data, so bodies are kept.
- Admin: Message, MessageLog, DontSendEntry registered; no first-class resend action beyond
  retrying deferred.
- Where it went wrong: deferred never auto-retries; two tables (queue then log) means moving rows;
  bodies kept in the log; pickled blobs historically.

## django-celery-email

- Data model: none. `CeleryEmailBackend` pickles messages (as dicts) into a Celery task
  `send_emails`, chunked by `CELERY_EMAIL_CHUNK_SIZE`.
- Retry: Celery task options via `CELERY_EMAIL_TASK_CONFIG` (`max_retries`, `default_retry_delay`,
  `rate_limit`, `ignore_result`). On exception it calls `self.retry(exc=...)`. The task retried is
  the whole chunk.
- Double-send: none. Chunk retry resends messages in the chunk that already succeeded when a later
  one fails. This is the known flaw: at-least-once with whole-batch granularity. Per-message rows
  fix it.
- Storage/admin: none; state lives in broker and result backend. "Did this person get their mail"
  is unanswerable, which is exactly the gap this spec closes.

## django-anymail

- Not a queue. It is the transport library. Relevant bits:
  - `send_messages()` returns the number sent; `message.anymail_status` carries `status` (set of
    `sent`, `queued`, `rejected`, `invalid`, `failed`, `unknown`), `message_id`, and per-recipient
    `recipients[addr].status/message_id`, and `esp_response`.
  - Errors: `AnymailAPIError` (with `status_code`, `response`), `AnymailRecipientsRefused` (all
    recipients rejected), `AnymailSerializationError`, `AnymailUnsupportedFeature`,
    `AnymailInvalidAddress`. Distinguishing API/transient from recipient/permanent errors is
    possible by class and `status_code`.
  - Tracking webhooks (delivered, bounced, complained) emit signals keyed by `message_id`; storing
    `message_id` on the outbox row is what lets later work correlate bounces (out of scope here but
    cheap to leave room for).
- Lessons for us: record `message_id`/status when the backend supplies it; `0` returned or
  `rejected` status without exception should count as failure; classify permanent (rejected, invalid,
  4xx) vs transient (5xx, connection, 429) so permanent failures skip the retry ladder.

## Rails ActionMailer `deliver_later` and ActiveJob `retry_on`

- Data model: whichever queue backend. `deliver_later` serialises mailer class, method and args
  (GlobalID for records) into a `ActionMailer::MailDeliveryJob`. Because args are references, the
  body is rendered at perform time, so there is no stored body; a rolled-back record fails
  deserialisation (`ActiveJob::DeserializationError`, discarded).
- Retry: `retry_on SomeError, wait: :polynomially_longer, attempts: 5` (default 5 attempts, wait
  grows roughly as attempt^4 + 2 s plus jitter in Rails 7.1+). `discard_on` for permanent errors.
  `config.action_mailer.delivery_job` can be subclassed to set `retry_on Net::SMTPServerBusy,
  Net::OpenTimeout` etc. By default `deliver_later` has no retry; people add it.
- Double-send: none; at-least-once. Rails docs say jobs must be idempotent. After retries exhaust,
  the exception hits the backend's dead set (Sidekiq Dead, GoodJob discarded, Solid Queue failed
  executions).
- Storage/admin: backend dependent. Sidekiq Web, Mission Control for Solid Queue/Resque offer
  retry/discard buttons.
- Where it went wrong / lessons: Enqueueing before commit caused a job that runs before the row
  exists; Rails added `enqueue_after_transaction_commit` (7.2) which matches our decision to
  enqueue on commit. Rendering at perform time means the content can differ from what was
  requested; we store the rendered message, which avoids that but carries the secret.

## Laravel queued mail

- Data model: `Mail::queue()` / `ShouldQueue` mailables become jobs in `jobs`; exhausted jobs land
  in `failed_jobs` (uuid, connection, queue, payload, exception, failed_at).
- Retry: `public $tries`, `public $backoff = [60, 300, 900]` (array = per-attempt delay, last
  repeats), `retryUntil()` for a time window (closest to our "about 2 hours" policy),
  `$maxExceptions`, `$timeout`, `$failOnTimeout`. `php artisan queue:retry all|uuid`,
  `queue:prune-failed --hours=`, `queue:flush`.
- Double-send: none; at-least-once. Docs say to use `afterCommit` (`$afterCommit = true` or
  `Mail::...->afterCommit()`) so jobs only dispatch after the transaction commits, the same
  decision we made. Known foot-gun: a timed-out job that actually sent gets retried and the mail
  goes twice; mitigation is `$timeout` shorter than the retry-after of the queue.
- Storage: failed payload (full serialised mailable) kept until pruned; `queue:prune-failed` is
  opt-in via schedule. Same retention-of-secrets issue as post-office.
- Admin: CLI, plus Horizon for Redis queues. Nova/Filament plugins for `failed_jobs`.
- Mistake: `failed_jobs` is a graveyard that needs manual `queue:retry`; automatic retry is only
  within the `tries` window.

## Transactional outbox (Discourse, GitLab and the pattern)

- Pattern: write business change and an outbox row in one transaction; a relay polls unsent rows
  and publishes, marks them sent. Delivery is at-least-once; consumers dedupe by id. This is the
  closest analogue to our persisted row per message, with the DB row (not the broker) as truth.
- Discourse: `email_logs` (sent record, `message_id`, `bounced`, user) and `skipped_email_logs`;
  jobs via Sidekiq with `Jobs::UserEmail`; `Email::Sender` builds the message and sets a
  `Message-ID` it stores, so incoming bounces correlate (`email_logs.bounce_key`). Emails are built at
  send time from user/post ids, not stored with body. Retry is Sidekiq's default (about 25 tries
  over ~21 days) which is long enough that stale notifications are sent late; Discourse added
  `Jobs::UserEmail` skip logic for stale mail. Lesson: a retry window must respect that mail goes
  stale, hence a bounded window (2 hours here).
- GitLab: webhooks are the nearest outbox. `WebHookLog` records each delivery (request/response,
  status, execution duration) and a webhook gets *disabled* after repeated failures with a
  progressive backoff (temporarily disabled, escalating, then permanently disabled), with
  `recent_failures`, `backoff_count`, `disabled_until`. Retention: `web_hook_logs` partitioned and
  pruned after ~90 days (daily partitions dropped). Admin: logs UI with a manual "Resend request".
  Lesson: a state machine of attempting, backed off, disabled with timestamps the scheduler really
  reads; and keep request headers sanitised in logs (they redact secrets). Our analogue: `next_retry_at`
  read by a scheduled task.
- Relay safety: Debezium-style or `SELECT ... FOR UPDATE SKIP LOCKED` claim so two relays do not take
  the same row; Postgres 17 supports this and Django exposes `select_for_update(skip_locked=True)`.

## Cross-cutting findings for the spec

1. Row per message with per-attempt count and `next_retry_at` that a scheduled task reads. Systems
   that record the state but have no driver (django-mailer deferred, Laravel failed_jobs, our own
   `WebhookDelivery.next_retry_at`) stall.
2. Atomic claim before send (`select_for_update(skip_locked=True)` plus a status flip to `sending`)
   with a stale-`sending` reclaim after a timeout, otherwise a killed worker leaves a row stuck.
   Post-office and celery-email both had duplicate-send races; none gets exactly-once. Accept
   at-least-once and say so; the worst case is a rare duplicate after a crash between provider
   accept and the DB commit.
3. Per-message, not per-batch, granularity (celery-email chunk retries resend good mail).
4. Classify errors: permanent (invalid or refused recipient, 5xx SMTP 55x) go straight to dead;
   transient (connect, timeout, 4xx SMTP, 421/450/451/452) retry. Anymail and Rails `discard_on`
   do this; post-office does not.
5. Treat "0 sent" and anymail `rejected` as failures, not successes.
6. Bounded retry window with a backoff ladder (Laravel `retryUntil`, `$backoff` array) rather than
   Discourse's three weeks; about 2 hours and about 6 attempts, e.g. 1, 5, 15, 30, 60 minutes, plus
   jitter.
7. Scrub the payload on success. Nobody here does it by default: post-office, django-mailer
   (`MessageLog`), Laravel (`failed_jobs`) and GitLab (logs, partially redacted) all keep bodies until
   a prune job. Keep operational columns: recipients (or a hash), subject, timestamps, attempt count,
   last error, provider `message_id`. Decide separately what to do with a dead row's payload (needed
   for admin resend, so retain until the housekeeping retention then scrub).
8. Retention: every system that retained rows needed a scheduled prune (`cleanup_mail`,
   `purge_mail_log`, `queue:prune-failed`, GitLab partition drop). Put pruning in
   `fls_run_housekeeping` from day one.
9. Enqueue on commit: Rails 7.2 `enqueue_after_transaction_commit` and Laravel `afterCommit` converge
   on the decision already made. In Django that is `transaction.on_commit`. Create the row inside the
   transaction; enqueue the task from `on_commit`; the sweep also picks up any `queued` row whose task
   never ran.
10. Admin: status filter, per-attempt log or at least last error, bulk "resend" that resets status and
    attempt count and re-enqueues (post-office requeue, GitLab resend). Make resend idempotent
    against an in-flight row (refuse if `sending`).
11. Store the provider `message_id` when available (anymail `anymail_status.message_id`, Discourse
    `Message-ID`); cheap, and it unlocks the out-of-scope bounce work later.

## References

- https://github.com/ui/django-post-office and https://django-post-office.readthedocs.io/ (models, settings `MAX_RETRIES`/`RETRY_INTERVAL`, `cleanup_mail`)
- https://github.com/pinax/django-mailer and https://django-mailer.readthedocs.io/ (`send_mail`, `retry_deferred`, `purge_mail_log`)
- https://github.com/pmclanahan/django-celery-email
- https://anymail.dev/en/stable/sending/anymail_additions/ (status, message_id) and https://anymail.dev/en/stable/sending/exceptions/
- https://api.rubyonrails.org/classes/ActiveJob/Exceptions/ClassMethods.html (`retry_on`, `discard_on`)
- https://guides.rubyonrails.org/active_job_basics.html and https://guides.rubyonrails.org/action_mailer_basics.html (`deliver_later`)
- https://laravel.com/docs/queues (tries, backoff, `retryUntil`, `afterCommit`, failed jobs, `queue:prune-failed`) and https://laravel.com/docs/mail#queueing-mail
- https://microservices.io/patterns/data/transactional-outbox.html
- https://github.com/discourse/discourse (`app/jobs/regular/user_email.rb`, `lib/email/sender.rb`, `EmailLog`)
- https://docs.gitlab.com/ee/user/project/integrations/webhooks.html (auto-disabling, backoff, logs, resend)

status: ok
