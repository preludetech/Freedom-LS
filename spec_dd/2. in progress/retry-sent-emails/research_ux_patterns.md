# Research: UX patterns for an email outbox admin surface

Topic `ux_patterns`, for the retry-sent-emails spec. Scope: the operator/admin surface (Django admin,
unfold). End-user "resend" patterns are context only; no learner-facing UI is planned.

Evidence quality: the repo findings were read from source. Product findings marked (web) come from
the cited pages or search snippets. Findings marked (recollection) are from memory of the products and
were not re-verified this session (fetches of the django-post-office and Postmark support pages
returned 404, and no Mailgun, SendGrid or Discourse page was fetched).

## 1. Repo conventions that constrain the design

- `.claude/ds/config.md` sets `Admin theme: unfold`. `claude_plugins/fls-dev/resources/admin_interface.md`
  says to read `admin_unfold.md` first, and that every site-aware model uses `SiteAwareModelAdmin`
  (`freedom_ls/site_aware_models/admin.py`, inherits `unfold.admin.ModelAdmin`, excludes `site`).
  If the outbox row is not site-aware (mail is transport-level), use `unfold.admin.ModelAdmin`
  directly; do not use `admin.ModelAdmin` (renders unstyled).
  `claude_plugins/django-stack/resources/admin_unfold.md` has the rules.
- `freedom_ls/webhooks/admin.py` is the closest in-repo precedent and should be mirrored:
  - `WebhookDeliveryAdmin`: `list_select_related`, `list_display` of type / target / `status` /
    `attempt_count` / `last_status_code` / `last_attempt_at`, `list_filter` on `status`, every field
    `readonly_fields`, `has_add/change/delete_permission` all False, and a bulk action
    `retry_deliveries` ("Retry failed/stuck/dead-lettered deliveries") that resets `attempt_count`
    and calls the delivery function inline.
  - `WebhookEndpointAdmin` uses unfold's `@unfold_action` with `actions_detail` for a per-object
    button ("Send Test"), and `django.contrib.messages` for feedback.
  - The existing retry action does not message the operator at all (no count, no skipped-count).
    That is a gap to avoid copying.
- Unfold is installed with `unfold.contrib.filters` (so `list_filter` can use unfold's richer filters,
  e.g. dropdown, date-range) and `unfold.contrib.import_export`. `SiteAwareExportModelAdmin` gives a
  CSV export action and button gated on view permission; an outbox could reuse it for "export failures
  for support", but recipient addresses are personal data, so decide deliberately (see section 6).
- Unfold supports `@display(label={...})` coloured badge columns (recollection; check the unfold docs
  for the installed >=0.83 API before specifying), `actions_list` (changelist-top buttons),
  `actions_row` (per-row), `actions_detail` (object page button; already used here) and
  `actions_submit_line`.

## 2. How products present an email log

(web) Postmark: activity feed with a per-message detail view showing content, the SMTP response from
the recipient server and delivery status; default retention is 45 days, adjustable 7-365 days; after
expiry the message and activity are gone from UI and API; the API returns an empty `Body` when no dump
is available; Postmark itself retries most domains every 10 minutes for up to 12 hours before
bouncing. The Postmark UI also lets an operator retry or re-send bounced mail after fixing the cause
(recollection of the support article; the page was not fetchable).
- https://postmarkapp.com/support/article/1267-why-didn-t-this-recipient-receive-my-message
- https://postmarkapp.com/blog/access-45-days-of-your-transactional-email-content-and-events
- https://postmarkapp.com/developer/api/messages-api
- https://postmarkapp.com/updates/upcoming-changes-to-bounce-message-retention

(web, partial) django-post-office: `Email` model with status (sent / failed / queued / requeued),
a `Log` model recording each delivery attempt with status, message and exception type, admin that can
requeue multiple emails at once, `LOG_LEVEL` to log only failures or all attempts, and
`MAX_RETRIES` / `RETRY_INTERVAL` settings. Exact admin action label unverified.
- https://pypi.org/project/django-post-office/3.0.4
- https://github-redirect.dependabot.com/JiriKr/django-post_office/blob/master/CHANGELOG.md

(recollection, unverified) SendGrid Email Activity feed, Mailgun Logs and Discourse `/admin/email`:
- SendGrid / Mailgun: a time-ordered event list (processed / delivered / deferred / bounced /
  dropped), filterable by recipient, status and date range, with a detail drawer showing the event
  timeline and provider response text. Message content in SendGrid is an opt-in paid add-on. These
  products show the provider side; ours is the app-side outbox, which is the analogue of Postmark's
  "queued/processed" stage.
- Discourse: `/admin/email` has tabs Sent / Skipped / Bounced / Received / Rejected, a filter box
  (user, address, type, reply key), per-row type and recipient, and a "skipped" tab with a reason
  column. Takeaways: a reason column for non-sends is valuable, and separating states into tabs
  or a status filter beats one undifferentiated list.

## 3. Common list-view pattern

Columns operators actually use (consistent across the above): recipient (To), subject, status badge,
attempt count, created / last attempt / next retry time, short last-error text.
- Status badge: a small closed set, colour-coded. For this spec the natural set follows the retry
  model: pending/queued, sent, retrying (failed, will retry), dead (retries exhausted). Keep the
  displayed set identical to the stored statuses; do not invent display-only states.
- "Next retry" shown only for retrying rows; blank otherwise. Directly addresses the
  `WebhookDelivery.next_retry_at` lesson (a field no one reads).
- Filters: status (the primary one), created date (hierarchy or range), optionally "has error" /
  category. Search: recipient and subject (`search_fields`). Default ordering newest first.
  Default view should make dead rows easy to find: a status filter pre-set is not available in
  Django admin without custom code, so a one-click "Dead" filter link is the practical equivalent.
- Recipients are `to`/`cc`/`bcc` lists, so search on a flattened `recipients` text column or a first
  recipient column; a JSON array search is awkward. Worth deciding at spec time whether to store a
  denormalised recipient string.
- Truncate long error text in the list; full text on the detail page.
- Performance: the outbox grows without bound; `list_select_related` as in webhooks, index on
  status and created, `show_full_result_count = False` for large tables, and a retention/purge
  story (Postmark's 45-day default is the product precedent).

## 4. Detail view

All of it read-only (mirrors `WebhookDeliveryAdmin`):
- Header facts: status, recipients, subject, from, created, sent-at, attempt count, next retry.
- Last error (and ideally the exception type), shown in a monospace block, because it is the first
  thing an operator wants.
- Attempt history: django-post-office keeps a separate `Log` row per attempt; the webhooks app keeps
  only `last_*` fields on the row. Options: (a) last-attempt fields only (cheapest, matches webhooks);
  (b) an attempt child model shown as a read-only `TabularInline`. Attempt history only matters if
  operators need to see that attempt 3 failed differently from attempt 6; a single `last_error` plus
  `attempt_count` is the minimum viable and the idea.md does not ask for more. Flag as a decision.
- Link to the related task result (the `django_tasks_db` row) if one exists, as a debugging aid.
- Body panel: see section 5. Show an explicit placeholder rather than an empty box.

## 5. What "resend" means once the body is scrubbed

This is the main UX risk. The idea says the payload is blanked on send, so a row in status sent has
nothing to resend. Patterns seen:
- Postmark: once content has expired the message cannot be re-sent from the UI; the API returns an
  empty body (web, above). Content retention is explicit and visible.
- The honest options for this spec:
  1. Resend is only offered on rows whose payload still exists (retrying and dead rows). The action
     is hidden or refuses with a message for sent rows. This is consistent with the stated design:
     scrubbing happens on success, so only unsent rows keep a body. Recommended as the default.
  2. "Resend" on a sent row is a different operation: the caller must regenerate the mail (e.g.
     trigger a fresh password reset). The outbox cannot do this generically. Out of scope; the
     detail page should say "Body removed after sending; to send again, repeat the original action."
  3. Keep bodies for a window then scrub. Rejected by the settled constraint (reset links in bodies).
- Because the reset link is in the body, also consider that a dead row older than the link's
  validity (allauth reset tokens, default 3 days) is a stale resend: the mail would send a dead
  link. Show created-age in the detail page and consider a confirmation warning when old.
- Idempotency/safety: a resend of a row currently being worked by a worker risks a double send.
  The action should act only on non-in-flight states and use a row lock or a conditional update
  (`filter(status=...).update(...)`), reporting how many were actually re-queued.

## 6. Actions, confirmation and feedback

- Retry-now / resend should not send inline in the request (the webhooks action does, which blocks
  the admin on SMTP and can time out for a bulk selection). Preferred: the action resets state
  (status back to pending, `next_retry_at` now, optionally attempt count reset so a dead row gets a
  fresh ladder) and enqueues the send task; the request returns immediately. Operator sees the
  result by refreshing the list.
- Confirmation: Django admin actions run immediately on the changelist unless they render an
  intermediate page (as `delete_selected` does). Resend is cheap and reversible-ish (worst case an
  extra email), so no confirmation page for small selections is the common choice (django-post-office
  and the webhooks precedent both have none). Add a confirmation page only for a large selection
  (say, over a threshold) or when any selected row is stale (section 5). Unfold supports actions with
  intermediate forms if needed (verify in the installed unfold version).
- Feedback: always `messages.success` with the number re-queued and `messages.warning` with the
  number skipped and why ("3 skipped: already sent, nothing to resend"). The existing webhooks action
  gives no feedback, which is the pattern to improve on. Use the message level to match outcome (all
  skipped is a warning or error, not a success).
- Per-object vs bulk: provide both. `actions` for bulk on the changelist and `actions_detail`
  ("Resend now") on the object page, as `send_test_action` does.
- Permissions: gate on a dedicated permission or the change permission. The webhooks admin
  disables change permission entirely (so an action gated on change would be unavailable). Use
  `@admin.action(permissions=[...])` with a custom permission, e.g. `resend`, rather than reopening
  `has_change_permission`.
- Audit: log who resent what with Django's `LogEntry` (`ModelAdmin.log_change`) so there is an
  operator trail; cheap and idiomatic.
- Bulk-resend ceiling: a "retry everything dead" after a provider outage is the real bulk case.
  Selecting all across pages (Django's "select all N") works but can enqueue thousands at once; the
  enqueue should respect the retry scheduler's throughput, i.e. set `next_retry_at` and let the
  scheduled sweep drain rather than send all inline. This also keeps the admin action consistent with
  the automatic path (one send path).
- Edge: do not let the operator edit recipients or body. Read-only everywhere; no add/change/delete
  permission, per the webhooks precedent. Delete may be needed for housekeeping; handle by a purge
  task, not the admin.

## 7. End-user context ("didn't get the email? resend")

Context only. Common pattern on auth mail screens: after submit, a neutral confirmation ("If an
account exists, we have sent instructions") that never confirms whether the address exists, plus a
resend link with a cooldown (30-60 seconds) and rate limit. The user resend always generates a fresh
token and fresh mail rather than re-sending a stored body, which is consistent with the scrub-on-send
decision. Nothing in this spec needs it; the outbox should not leak per-address delivery state to
unauthenticated users.

## 8. Recommendation summary (what fits FLS)

1. One read-only `unfold.admin.ModelAdmin` for the outbox row, modelled on `WebhookDeliveryAdmin`:
   status badge, recipient, subject, attempt count, next retry, last attempt, truncated error;
   `list_filter` on status and created date; `search_fields` on recipient and subject; no add, change
   or delete permission.
2. Detail page with last error, timing, task link, and an explicit "body removed after sending" note.
3. Resend as both a bulk action and a detail button; offered only for unsent rows; resets to pending
   and lets the scheduled sweep or task drain it; always reports re-queued and skipped counts.
4. Decide at spec time: attempt history (inline model) vs last-error only; stored recipient string
   for search; purge/retention window; custom `resend` permission; whether any confirmation page.
5. Do not reuse the webhooks action's inline-send and silent-feedback behaviour.

## References

- https://postmarkapp.com/support/article/1267-why-didn-t-this-recipient-receive-my-message
- https://postmarkapp.com/blog/access-45-days-of-your-transactional-email-content-and-events
- https://postmarkapp.com/developer/api/messages-api
- https://postmarkapp.com/updates/upcoming-changes-to-bounce-message-retention
- https://pypi.org/project/django-post-office/3.0.4
- https://github-redirect.dependabot.com/JiriKr/django-post_office/blob/master/CHANGELOG.md
- Repo: `freedom_ls/webhooks/admin.py`, `claude_plugins/fls-dev/resources/admin_interface.md`,
  `claude_plugins/django-stack/resources/admin_unfold.md`, `config/settings_base.py` (unfold apps)

status: ok
