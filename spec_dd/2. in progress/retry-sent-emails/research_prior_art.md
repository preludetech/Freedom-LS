# Research: prior art for retry-sent-emails

Question: what has already been tried for this, here or elsewhere, and what happened?

Limits: this worker has no shell, so `git log --oneline -- freedom_ls/mail freedom_ls/webhooks`
was not run. History below comes from the done and in-progress specs plus the current code. The
external incident section is from search snippets, not full reads of each page.

## 1. Here: what already exists

### The mail queue (QueuedEmailBackend) introduction

- Landed in `spec_dd/3. done/2026-09-07_18:13_misc-small-fixes-manual/` (`upgrade_notes.md`,
  `qa_report.md` section 2, `todo.md`). Moved from `deployment.mail` to `freedom_ls/mail`.
- Decided: `EMAIL_BACKEND` names the queue and `EMAIL_UPSTREAM_BACKEND` names what the worker
  really sends through. Pointing the upstream at the queue is caught at boot by
  `freedom_ls_mail.E001`. Mail goes at priority 10, ahead of the 0 used by webhook delivery and
  reports. `EMAIL_TIMEOUT` is recommended so a hung SMTP session cannot stall the single worker.
- Decided: queueing is opt-in in production (`config/settings_prod.py:106-110` defaults
  `EMAIL_BACKEND` to direct SMTP). Dev opts in (`config/settings_dev.py:94`). The reason given was
  that queued mail with no worker behind it is accepted and never sent.
  - Consequence for this spec: `idea.md` says `QueuedEmailBackend` "is already `EMAIL_BACKEND`",
    which is true in dev only. A production deployment on the default gets no outbox and no retry
    from this work. `oldspec.md` handles this in its `upgrade_notes.md` line; the new spec should
    keep that sentence.
- Decided: mail is always sent inside a request, so the off-request site resolution (SITE_ID
  probe, single-Site fallback) was removed as scope creep (`todo.md:55`). That bears on
  `OutboundEmail.site` being nullable and best-effort. The new spec should not reintroduce
  off-request site guessing beyond what the existing helper does.
- Verified in QA: gate 2.16 passed. With the queue configured and no worker, a password reset
  completes in the browser, no mail arrives, and an unpicked task row sits in the DB. This is the
  silent failure the later worker/housekeeping work was built to expose. Starting the worker
  delivered the mail intact (8bit encoding, unbroken URL).
- Left out then: any retry, any persistence beyond the `DBTaskResult` row. The QA report names
  the `retry-sent-emails` spec as intended collateral (13.6), so retry was deliberately deferred,
  not forgotten.
- Current code: `freedom_ls/mail/backends.py` puts the full serialised payload in the task args.
  `freedom_ls/mail/tasks.py` `send_serialised_email` discards the return of
  `connection.send_messages`. There is no `models.py` or `migrations/` in `freedom_ls/mail/`.

### Worker watchdog and housekeeping

Source: `spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/` (`1. spec.md`, `research_worker_heartbeat.md`,
`research_housekeeping_command.md`) and its follow-ups; code in `freedom_ls/deployment/`.

- Decided: a watchdog thread that exits the process directly (`os._exit`), not `SIGALRM`, because
  `db_worker` would swallow the signal as a normal task failure. A task is capped by
  `WORKER_MAX_TASK_SECONDS` / heartbeat window; a killed task keeps no bookkeeping.
- Decided: `fls_run_housekeeping` runs once and exits. The deployment supplies the schedule
  (downstream wrappers `run_housekeeping`). Each sweep sits in its own `try`, with
  `SWEEP_FAILURES = (CommandError, DatabaseError)`. Results split into `sweep_failures`,
  `findings` and `notes` via `HousekeepingOutcome`. Findings fail the exit code but do not
  withhold the heartbeat. Everything is safe to run twice.
- **Decided against requeueing an orphaned RUNNING task, explicitly because of email.** The
  prepare-to-deploy spec (orphan reap section) says resetting the row to unclaimed "is a one-line
  change and it is wrong: the row records that the task started, not how far it got, so a task
  killed between sending an email and recording that it sent one sends it twice." It closes the
  row with `OrphanedTaskError` and a Sentry message instead, putting a person in front of the
  decision. This is the direct precedent against `oldspec.md`'s stuck-`sending` recovery, which
  re-sends anyway (see section 3).
- Since then housekeeping has grown more sweeps (orphaned reports, stale previews, bulk-record
  runs). The roadmap notes `deadlines-5-reminders` and `file-scanning` add sweeps too, so the
  housekeeping module will keep growing and is a merge-collision zone.
- Pending neighbour: `spec_dd/1. next/housekeeping-sentry-cron-checkin/idea.md`. Once built,
  "housekeeping stopped running" becomes visible. That matters because retry certainty depends on
  housekeeping running.
- Constant-text Sentry messages with row detail on the scope, so a recurring fault groups into
  one issue, are the existing house style (`mark_orphaned_running_tasks_failed`).

### Webhooks delivery retry

Source: `spec_dd/3. done/2026-03-16_16:20_outward-webhooks/` (`1. spec.md` Retry and Resilience,
`2. plan.md`, `qa_report.md`) and `freedom_ls/webhooks/`.

- Decided: `RETRY_DELAYS = [60, 300, 1800, 7200, 43200]` with up to 20% jitter, response
  classification (2xx success, 429 honour `Retry-After`, other 4xx permanent, 5xx/timeout/connection
  retry), `dead_letter` after max attempts, an admin "retry deliveries" action, and a circuit
  breaker on endpoints. Research picked these from Hookdeck, Svix, Stripe and AWS guidance.
- **Flaw to avoid: `WebhookDelivery.next_retry_at` is written and never read by anything that
  acts.** A grep of `freedom_ls/` shows it set in `delivery.py` (lines 183-214), listed in
  `admin.py:218`, and asserted in tests. No task, sweep or command selects rows by it. The spec
  said "the task schedules a retry with exponential backoff", but the field only stores a time. An
  admin click is the only thing that re-drives a delivery. `idea.md` already names this; the new
  spec's success criteria must include a test where an unattended due row is picked up.
- QA note (`qa_report.md` Issue 1): the admin retry resets `attempt_count` to 1 instead of
  incrementing, which QA flagged as ambiguous. `oldspec.md`'s resend action resets to 0 on
  purpose. The new spec should state which it means and why, so QA does not re-raise it.
- The admin action retries inline (`retry_deliveries`, `admin.py:253`), holding the admin request
  open. `oldspec.md` rejects this for mail; keep that.
- `calculate_next_retry` (`delivery.py:230`) is the jitter helper `oldspec.md` chose to copy
  rather than import, to keep the dependency arrow out of a product app. Still sensible.
- Out of scope in `oldspec.md`: fixing the webhooks flaw. Still out; `idea.md` only says not to
  repeat it.

### Related in-flight specs that depend on this one

- `spec_dd/1. next/user-communication-2-notification-email/idea.md` is blocked by this spec. It
  says "This spec adds no retry, persistence or failure handling of its own", needs the queued
  backend as a deployment requirement "in the same terms `retry-sent-emails` uses", and takes the
  "at least hourly" housekeeping cadence wording from this spec. It also reads
  `spec_dd/1. next/retry-sent-emails/1. spec.md`, a path that does not exist now. The spec lives
  in `2. in progress/`. When this spec is written, the path or name used there should be fixed or
  at least flagged. Account mail (allauth) is declared "untouched", never digested, ignores quiet
  hours.
- `spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/research_delivery_backend_seam.md`
  records the project preference for `transaction.on_commit` around outward side effects (the
  `course.registered` hook), and that `fire_webhook_event` inserts its event row synchronously
  and enqueues a task carrying only ids plus `site_id`. This is the same shape `oldspec.md`
  proposes (row, then enqueue on commit, task carries the id).
- Roadmap (`spec_dd/1. next/roadmap.md`): `retry-sent-emails` is "Tooling and operations", and
  the transport for `user-communication-2`. It collides on `housekeeping.py` with
  `deadlines-5-reminders` and `file-scanning`.

## 2. oldspec.md: decisions and what has overtaken them

Summary of the September spec: a persisted `OutboundEmail` row per message, owned by
`QueuedEmailBackend`, with a UUID task argument only; error classification into transient,
permanent and neither; one task per attempt with deferred `run_after` and a local backoff ladder;
two housekeeping sweeps (due rows, stuck `sending` rows) plus a prune/scrub sweep; payload blanked
on success; a read-only admin with a resend action; settings in `freedom_ls/mail/config.py`; pinned
`Message-ID` for dedup; a check warning when the task backend cannot defer.

Per `answers.md`, the new spec treats it as prior art: keep what still matches, re-derive the rest.

| Oldspec decision | Status now |
| --- | --- |
| Row per message, not a counter in the payload; task carries only the id | Kept. `idea.md` restates it. Current backend still puts the whole payload in task args, so the change is still needed. |
| Payload blanked on success, recipients/subject/`message_id` kept | Kept (`idea.md`). |
| Not a `SiteAwareModel`, not a `TimestampedModel`, nullable `site` | Still plausible; re-check against the current conformance test (`freedom_ls/contrib/conformance/tests/test_timestamped_models.py`) and `docs/app_structure.md`. |
| Rolled-back enqueue: row inside the transaction, enqueue on commit, discard by design | Confirmed by `answers.md` (user decided). Matches the `on_commit` house pattern. |
| Retry horizon: 7 attempts, ladder `[60, 300, 900, 3600, 10800, 21600]` (about 10 hours of backoff) | **Overtaken.** User now wants about 2 hours and roughly 6 attempts. Ladder, `EMAIL_MAX_ATTEMPTS` and the config relationship tests need re-deriving. The old rationale (verification keys last 3 days; mail half a day late is mostly useless) supports the shorter window too. |
| Dead-letter after the cap, admin resend afterwards | Kept in shape (user: "marked dead and left for the admin resend"). |
| Bounce/complaint feedback out of scope | Confirmed, "its own idea" (`answers.md`). |
| Stuck `sending` rows are re-sent anyway, accepting duplicates | **Contested.** Contradicts the prepare-to-deploy orphan-reap rule (never requeue a task killed mid-send, since mail may already be delivered). Oldspec argues a lost verification mail is worse than a duplicate, and pins `Message-ID` to mitigate. Needs an explicit decision, and the orphan reap will race it: the existing reap closes the same `DBTaskResult` as FAILED with a Sentry message at 3600s. Check both windows and who wins. |
| Two drivers (deferred task plus housekeeping sweep) | Kept in intent (`idea.md`: "scheduled task and housekeeping sweep behind it"). Guard on `supports_defer` for `ImmediateBackend` (dev/test) still needed; verify it against the pinned `django-tasks` 0.12.0 and the current `TASKS` blocks (`config/settings_base.py:615`, `settings_prod.py:87`). |
| `EmailNotSentError` for a send returning 0; `fail_silently=False` explicit | Kept as a gap in `idea.md`. **Name collision:** `backends.py` already defines `QueuedEmailNotSentError` (inline-backend failure surfaced to the caller). Oldspec's `EmailNotSentError` and the `mail.py` it names do not exist; the module is `serialisation.py`. Decide on one naming scheme. |
| Cited line numbers (`settings_base.py:404`, `housekeeping.py:102`, `config.py:56`, `settings_base.py:493`) | Stale. `ACCOUNT_EMAIL_VERIFICATION` is now at `settings_base.py:437`, `TASKS` at `:615`, the orphan reap at `housekeeping.py:107`, and the ceiling-rule comment is in `freedom_ls/deployment/config.py`, not `freedom_ls/mail/config.py`. Re-cite from code. |
| `freedom_ls/mail/config.py` gains the retry settings | Still correct that the file holds only `EMAIL_UPSTREAM_BACKEND` today. |
| Local backoff helper rather than importing from `webhooks` | Kept; no reason has changed. |
| Admin: read-only, no payload shown, resend action that enqueues rather than sends inline | Kept. Resend resetting `attempt_count` to 0 vs the webhooks QA issue noted above. |
| Docs: `docs/product/deployment.md:13` "fails silently" and recommended cadence | Re-check wording; user-communication-2 expects "at least hourly" from this spec. |
| Open questions: retention of 30 days / 3 days to check against `legal_docs/`; digest of undelivered mail | Still open. |

## 3. Lessons to carry into the new spec

1. A retry time stored in a column is not a retry. The sweep that reads it is the feature
   (`WebhookDelivery.next_retry_at`). Test it with no admin involvement.
2. A task killed after the provider accepts the message and before the DB write looks unsent.
   The repo already chose, once, to close such rows and tell a human. Any reversal needs its own
   reasoning and a duplicate-mitigation (pinned `Message-ID`, short window).
3. Housekeeping is the backstop but only exists if someone schedules it. Retry certainty is only
   as strong as that schedule; the Sentry-cron-checkin idea is the safety net for noticing it
   stopped.
4. Production defaults to direct SMTP. Value delivered by this work only reaches a deployment that
   opts in; say so in upgrade notes and docs.
5. Keep ladders short for mail: tokens and impatient users make late mail useless. The user has
   now chosen about 2 hours.
6. Housekeeping sweeps are accumulating in one module. Expect rebase collisions with
   `deadlines-5-reminders` and `file-scanning`; add email sweeps as small functions in the
   established try/except style.

## 4. Elsewhere: incidents and write-ups

These are from search results and snippets; verify details before quoting.

- Duplicate sends from a crash between provider accept and the success write: Mailgun describes
  an ungraceful restart where messages were sent but not recorded as delivered, then retried
  (https://www.mailgun.com/?p=4687). Buttondown's duplicate-sends postmortem is another real
  case (https://buttondown.com/blog/incident-0021). Root cause was not visible in the snippet.
- Mass duplicate email from a task-queue fault: SourceLair post-mortem
  (https://www.sourcelair.com/blog/articles/66/post-mortem-why-several-users-got-spammed-with-emails).
- Delivery queue backup and delayed mail when a recipient domain failed:
  https://improvmx.com/blog/post-mortem-backed-up-delivery-queue and Buttondown's backlog
  postmortem (https://buttondown.com/blog/incident-0016).
- Celery: at-least-once delivery with `acks_late` and a Redis visibility timeout shorter than the
  task causes the same message to run twice
  (https://dev.to/polly_colson_e4498b3f8e1c/celery-retries-keep-duplicating-after-redis-visibility-timeout-490f,
  https://python.plainenglish.io/python-celery-early-ack-turned-one-worker-crash-into-47-duplicate-refunds-04abbf7eda4d).
  Default early ack instead loses tasks on a crash. This is the same trade-off section 2's
  stuck-row row is about.
- Recommended mitigations in these write-ups: a conditional update that only writes when the
  send timestamp is still empty (the claim `UPDATE` in `oldspec.md`), a stable per-message ID so
  receivers dedupe (the pinned `Message-ID`), and claims with a TTL where too short allows
  duplicates and too long delays recovery (https://notes.kodekloud.com/docs/System-Design-for-Interview-Prep/Fan-Out-One-Event-Many-Readers/Notification-System-The-Duplicate-Trap/page,
  https://dev.to/kevindev27/idempotent-signup-emails-in-nodejs-apis-2k4m).
- Gap: no source found on retry after a `transaction.on_commit` rollback race. The Django docs on
  `on_commit` are the authority for that behaviour
  (https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit).

status: ok
