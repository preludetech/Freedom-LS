# Answers: retry sent emails

Asked by `/sdd:start` before the spec was written.

- Q: How should the new spec treat `oldspec.md`, the September spec? → A: As prior art, re-checked: keep its decisions where they still match today's code, re-derive the rest (asked up front)
- Q: What should happen to mail queued inside a transaction that rolls back? → A: Discard it by design: the row and the task commit with the transaction (task enqueued on commit), so a rolled-back action sends no mail and row and task stay consistent (asked up front)
- Q: How long should automatic retries run before a message is marked dead and left for the admin resend? → A: About 2 hours, roughly 6 attempts on a backoff ladder (asked up front)
- Q: Is delivery after the provider accepts the mail (bounces, complaints via provider webhooks) in scope? → A: Out of scope; it becomes its own idea (asked up front)
- Q: Who should see the outbox admin, given rows are not site-aware? → A: Superusers only (asked up front)
- Q: What should housekeeping do with a row stuck in `sending` after a worker died mid-send? → A: Re-send it (asked up front)
- Q: How long should the outbox keep rows and failed payloads? → A: Rows 30 days, failed payload 3 days, both as settings (asked up front)
- Q: Given the prepare-to-deploy precedent of never requeuing a task killed mid-run, should a stuck `sending` row still be re-sent? → A: Yes; mail gets its own rule, mitigated by a pinned Message-ID (asked while research ran)
- Q: Production defaults `EMAIL_BACKEND` to direct SMTP; change that? → A: Make `QueuedEmailBackend` the production default (asked while research ran)
