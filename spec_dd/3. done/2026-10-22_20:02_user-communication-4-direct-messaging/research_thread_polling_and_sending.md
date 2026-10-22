# Research: thread delivery over polling (new messages, older pages, safe sends)

Builds on `research_prior_django_messaging.md` (cursor pagination rationale, `intersect` sentinel) and
`spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/research_badge_polling_in_fls.md`.
Idea level: findings and recommendations. Prototype refs: `design_source/dm/dm-app.jsx`
(`poll`, `older`, `deliver`, `retry`, `discard`) and `dm-store.jsx` (`S.since`, `S.page`, idempotent `S.send`).

## Corrections to earlier research (read first)

1. **The shipped bell does not use an htmx `every` trigger.** The badge research recommended
   `hx-trigger="every 45s [document.visibilityState === 'visible'], ..."`. What shipped
   (`freedom_ls/comms/static/comms/js/alpine-components.js`, `notificationBell`) is an Alpine timer:
   `setInterval` dispatches a custom `refresh` DOM event on `#notification-badge`, whose
   `hx-trigger="refresh"` does the `hx-get`. A `visibilitychange` listener stops the timer when the tab is
   hidden and, on becoming visible, restarts it **and fires one immediate refresh**. Reason recorded in the
   file: the `@alpinejs/csp` build (and FLS's CSP) forbids inline filter expressions, so
   `[document.visibilityState === 'visible']` in an attribute is not available. Interval comes from
   `CommsConfig.NOTIFICATION_BADGE_POLL_SECONDS` (default 45) via `data-poll-seconds`. The view
   (`comms.views.notification_badge`, `@login_required_htmx`) renders only the small badge partial.
   **Thread and inbox polling must follow this same idiom**, not the `every ... [filter]` syntax.
2. **Message primary keys will be UUID4, so "cursor = `id__lt`" from the earlier research does not work.**
   `SiteAwareModel.id` is `UUIDField(default=uuid.uuid4)` (`site_aware_models/models.py:161`). UUID4 is random,
   not monotonic: `id__lt` neither orders by time nor excludes later rows. The cursor must be a keyset on
   `(created_at, id)`. Do not switch to timestamp-only (ties).

## 1. Polling: today, and what thread / inbox polls should do

### Today (bell)
- Interval 45s, per open tab, paused while hidden, one catch-up fetch on becoming visible. The badge is on
  every authenticated page, so the bell already costs one small indexed `COUNT` per tab per 45s.
- Per-poll cost beyond a normal authenticated GET is only the view's query: no extra middleware DB work
  (see the badge research section 3). No caching: production cache is DB-backed, so it saves nothing.
- Expiry: `login_required_htmx` gives 204 + `HX-Redirect` instead of a 302 that htmx would swap into the page.
  Thread polls need the same decorator, or an expired session swaps a login page into the message list.

### Recommended thread poll
- A hidden poller element inside the thread (`hx-get=<thread poll url>`, `hx-trigger="refresh"`,
  `hx-swap="none"`-style or a target that is the message list with `beforeend`), driven by the same
  visibility-aware timer idiom as the bell. Prefer reusing/generalising that timer rather than writing a
  second copy (project rule: avoid repeating code). Interval is its own setting (the thread is a live
  surface, so shorter than the 45s badge: roughly 5-10s while the thread is open and visible; a
  `CommsConfig` setting, same pattern as the badge one).
- Request carries the **newer cursor**: `?after=<created_at>_<id>` of the last message the client holds
  (read from a `data-` attribute on the last rendered message, updated by every swap). Query:
  `created_at > c OR (created_at = c AND id > i)`, `order_by("created_at", "id")`, capped (say 50).
  Equivalent Postgres row-comparison is not expressible in the ORM without `Q`; the `Q` form is fine and
  uses the index.
- Response:
  - Nothing new: **204 No Content**. htmx does not swap on 204, no DOM churn, no scroll/selection side
    effects, tiny response. (Existing FLS precedent: 204 is already the "nothing to render" answer.)
  - New messages: 200 with only the new message `<li>`s, `hx-swap="beforeend"` into the list. The response
    also carries the new "last cursor" because it is simply the last `<li>`'s data attribute.
  - **286** is the htmx "stop polling" status, and only affects htmx's own `every` triggers. Because FLS
    drives polling from an Alpine timer + custom event, 286 would do nothing. Use it only if a thread poll
    is ever moved to `hx-trigger="every Ns"`. For "thread closed by policy" prefer returning the swapped
    composer (see section 3) and letting the poll continue (history may still gain the other side's last
    message).
- Side effects of a thread poll: marking the thread read when it returns incoming messages (prototype does
  `S.markRead` on incoming). That makes the poll a write on some ticks; keep it to one `UPDATE ... WHERE
  recipient unread` guarded by the index, and only when the response actually contains messages from the
  other party. The 204 path must stay write-free.
- Include an `HX-Trigger` event (project convention, `htmx` skill "Domain events") such as a conversation
  changed event so the inbox list and header Messages unread count refresh immediately, instead of each
  waiting for its own tick. Or an OOB swap of the unread count in the same response (the bell panel already
  does this with `notification_badge.html` + `oob`).

### Recommended inbox poll
- Same timer idiom on the inbox list (and the header Messages unread count, which can share the bell's
  rhythm, 45s, since it is global and not second-sensitive). Send a cheap validator, not a cursor: the
  client sends the latest conversation `last_message_at` it has (`?since=`). Server answers 204 if no
  conversation the user is in has a newer `last_message_at`, else 200 with the re-rendered list
  (`outerHTML`; list is small, ordered by recency, so a full re-render beats merging rows).
- When a thread is open beside the inbox (desktop two-pane), the thread poll's `HX-Trigger` handles the open
  conversation's row immediately; the inbox timer only has to catch other conversations. Do **not** run both
  at the same cadence; the inbox can stay at ~30-45s while a thread polls at 5-10s.
- The shipped unread notification count (one notification per unread conversation, per the prototype's
  store) already refreshes the bell, so the header Messages link count and bell need not be tightly synced.

### Two cursors, one list
- Two independent cursors, each stored **in the DOM**, derived from what is rendered:
  - **older** cursor: `(created_at, id)` of the first rendered message, held on the "load earlier" control.
  - **newer** cursor: `(created_at, id)` of the last rendered message, held on the poller / last `<li>`.
  They only ever move outward, so they cannot cross: older pages are strictly before the first message,
  polls strictly after the last. A page that is prepended never changes the newer cursor, and an appended poll
  never changes the older cursor. This is why they stay correct together without server-side state.
- Prepending with htmx: "load earlier" is an `hx-get ?before=<cursor>` with `hx-swap="afterbegin"` targeting
  the list; the response includes a fresh "load earlier" control only when more exist (fetch `PAGE_SIZE+1`
  rows to know, rather than the `count()==PAGE_SIZE` guess in the earlier research, which shows a dead
  button when the last page is exactly full). Since the control lives inside the list, swap it
  `outerHTML` with the older rows + new control (`hx-target="this"`, `hx-swap="outerHTML"`), which also
  avoids leaving stale controls behind and obeys the skill's "prefer `outerHTML`".
- Empty first page: the poll needs a cursor even when the thread has no messages: send no `after` and let the
  server return the newest page, or use a sentinel `after=` of the thread open time. Prefer "no `after` -
  return everything since the initial page", which is just the first load.
- **Day separators and grouping** (design): these are render-time decisions that depend on the previous
  message. A `beforeend` fragment must know the previous message's day and sender. Pass them to the poll
  (`?after=` plus `last_day`/`last_sender`, or read them server-side from the cursor message), otherwise the
  fragment will repeat a separator or fail to group. Same for prepends: the boundary between older page and
  the existing first message may need a separator removed. Simplest: let the server re-derive from the cursor
  row; one extra indexed lookup.
- **Own messages arrive twice** (POST response and poll) unless prevented. Defences, all cheap:
  1. Every rendered message carries `id="msg-<uuid>"`. The poll fragment is rendered by the server from the
     DB, so it will include the user's own just-sent message if the poll's `after` cursor predates it.
     Dedupe must therefore be at the cursor, not by trusting the client.
  2. The POST response appends the new message and **moves the newer cursor** (same `data-` attribute /
     OOB update of the poller element), so the next poll's `after` already includes it. This removes the
     duplicate in the normal case without client JS.
  3. Race: poll request leaves with the old cursor, POST completes, poll response lands with the same
     message. With htmx's per-element request queue (default `hx-sync` on the same element is "drop"/"queue
     last" depending on trigger) this is narrow but real. Use `hx-sync` so that a poll in flight is aborted
     (`hx-sync="closest form:abort"` style on the composer, or `hx-sync="this:replace"` on the poller)
     when a send starts, and a small Alpine/htmx-event handler (CSP-safe, registered via `Alpine.data`)
     that removes later duplicates by `id` on `htmx:afterSettle`/`htmx:oobAfterSwap`. The prototype does it
     with `dmMerge` (id-keyed merge) plus matching `pending` by the idempotency `key` when the real message
     appears in the poll. FLS equivalent: the pending bubble is replaced by id/key, never both shown.
  Treat dedupe-by-id in the DOM as a belt-and-braces safety net; the cursor move in step 2 is the real fix.
- Out-of-order/clock: `created_at` is DB-assigned on insert (`auto_now_add`), so two messages inserted in
  concurrent transactions can commit out of order and a poll with `after=c` could permanently skip a
  message that committed later with an earlier timestamp. At 1:1 educator-learner volumes this is rare, but
  it is the one correctness hole of timestamp cursors. Mitigations, pick one: (a) re-query with a small
  overlap (`created_at > c - 2s`) and rely on id dedupe, which is cheap and makes the dedupe above mandatory,
  not optional; (b) a monotonically increasing `bigint` sequence column on the message for cursoring
  (sequence values are also assigned before commit, so it has the same hole, but with it plus overlap ties
  vanish). Recommendation: (a).

## 2. Scroll behaviour and announcements

### Stick to bottom vs "new messages" pill
- Decide **before** the swap whether the user is at the bottom (scrollTop + clientHeight within ~a few px of
  scrollHeight) via `htmx:beforeSwap`/`htmx:beforeRequest` on the list; record it. After `htmx:afterSettle`:
  if they were at the bottom, `scrollTo` the bottom; otherwise leave scroll untouched and show the
  "new messages" pill (count of added messages). Clicking the pill scrolls to bottom and hides it; scrolling
  to the bottom by hand also hides it.
- The pill is client-state, so Alpine (project rule: htmx for server interaction, Alpine for client state).
  Wire through `Alpine.data(...)` in `freedom_ls/comms/static/comms/js/alpine-components.js`; CSP build means
  no inline expressions, same constraint that shaped the bell.
- Your own sent message always scrolls to bottom, regardless of position (you just acted).
- Reduced motion: use `behavior: "auto"` when `prefers-reduced-motion: reduce`, else smooth.

### Prepending older messages without a jump
- Browsers with CSS scroll anchoring (Chrome, Firefox; Safari lacks it as of the sources checked) usually keep
  the viewport stable when content is inserted above it, but it must not be relied on. Reliable approach:
  on `htmx:beforeSwap` record `scrollHeight` and `scrollTop`; on `htmx:afterSettle` set
  `scrollTop = oldScrollTop + (newScrollHeight - oldScrollHeight)`.
- Prefer a **button** ("Load earlier messages", per the design) with `hx-trigger="click"` over an
  `intersect once` sentinel. Reasons: keyboard and screen reader users can reach and operate it; an
  auto-fire at the top interacts badly with scroll restoration (the new content pushes the sentinel out, but a
  restore that lands at the top re-triggers it in a loop); and focus handling is explicit. The earlier
  research's `intersect once` sentinel is acceptable only as an enhancement; the button remains the accessible path.
- After loading older messages, keep keyboard focus on the first newly loaded message (or the control's
  stable position), not lost to `<body>`.
- Initial open: scroll to the bottom (or first unread, if designed), done once on load.

### aria-live without spam (WCAG 2.2 SC 4.1.3 Status Messages)
- 4.1.3 requires status messages be programmatically determinable via role/properties **without receiving
  focus**. The FLS bell already uses `role="status"` (implicit `aria-live="polite"`, atomic).
- Do **not** put `aria-live` on the whole message list. Every `beforeend` swap would be announced as it
  appears, and prepending older messages (user-initiated) or the initial render would be read aloud in bulk.
- Use a **separate, visually hidden status region** (`role="status"`, empty at load), outside the swapped
  list, so it survives swaps. Write one short, summarised sentence into it only when a poll delivers messages
  from the other party: "New message from <name>" or "3 new messages from <name>". Coalesce multiple
  messages in one poll into one announcement; never read the body (the prototype announces the body, which
  can be long and is both noisy and sensitive in shared-screen contexts; recommend name + count only).
- Do not announce: your own sent messages, prepended older pages, the initial load, or 204s.
- Clear or overwrite the region text (and write after a short delay if re-announcing identical text) so a
  repeat of the same string still announces; live regions only announce on content change.
- Failure states ("Message not sent. Retry") are stronger: `role="alert"` on the failed bubble's message,
  as the prototype's `announce(...)` for failures does, and as FLS already does for 422s
  (`form_engine/.../answer_errors.html` uses `role="alert"` placed so it announces on the 422 re-render).
- Pill: it is a button ("2 new messages, jump to latest"); its appearance does not need its own live
  announcement if the status region already said it.

## 3. Safe-to-retry sending

### Why both an idempotency key and a disabled button
They defend different failures and one cannot substitute for the other:
- **`hx-disabled-elt`** (FLS already uses it, e.g. `panel_framework/modal/form.html`,
  `delete_confirmation.html`, `bulk_confirmation_form.html`, `cotton/modal-trigger.html`) prevents the
  accidental double-click / double-Enter **while a request is in flight**. It is client-side, per page, and
  gone on reload; it does nothing for a request that succeeded server-side whose response was lost, a retry
  after reload, two tabs, or htmx re-issuing. It also only disables for the life of one request, so a retry
  after failure is a *new* request that is not protected.
- **Idempotency key + unique constraint** makes the server tolerate the same send twice: the lost-response
  retry, the user pressing the "Retry" control, two tabs, a flaky proxy retrying a POST. Without it the
  button alone is a race, not a guarantee. Without the button, the unique key still protects the data but
  the UI shows a double-submit flicker and wasted requests, and `Enter` repeats could queue.
- So: button for UX and request economy, key for correctness. This matches the prototype: pending items
  carry a `key`, `S.send(..., key)` is idempotent, and the poll removes pending items whose `key` appears.

### Key design
- A hidden `<input type="hidden" name="client_key" value="<uuid4>">` rendered in the composer **per draft**.
  After a successful send, the response swaps in a fresh composer (new key, empty textarea). After a failure
  the composer/bubble keeps the **same** key so a retry is the same logical send.
- Message gets a nullable `client_key` UUID field with
  `UniqueConstraint(fields=["conversation", "sender", "client_key"], condition=Q(client_key__isnull=False))`
  (partial; FLS already uses `condition=` constraints). Scope it by sender (and conversation) so one user
  cannot probe or collide with another's keys, and so keys are not globally unique state.
- Send path: `get_or_create`-style by key inside the same transaction as the insert; on `IntegrityError` for
  the key, re-fetch and return the **original** message with a 200 (not 409, not a second insert). Catch the
  specific `IntegrityError`, per project convention. Handle the policy check **before** the key lookup? No:
  a retried send of an already-accepted message should return the original even if policy has since changed
  (the message already exists); so look up the key first, then run the policy for genuinely new sends.
- The body should also be validated once; a retry with the same key but a different body should return the
  original (the key identifies the send, not the content). No need to compare bodies.
- Key lifetime: the constraint is permanent (one column), no TTL job needed. Do not log, per project rule.

### Failed network send keeps the draft
- A network failure is not a 4xx: htmx fires `htmx:sendError` (no response) / `htmx:timeout`, and does
  **not** swap, so the textarea is untouched. Hold the sent text in the client-rendered pending bubble (or
  just leave it in the textarea) marked "Not sent" with **Retry** and **Discard** (design 03 B).
- Do not clear the textarea in an `hx-on::before-request`; clear it only in the success swap (the swapped-in
  fresh composer replaces the form `outerHTML`). That ordering is what keeps the draft on failure without
  extra code. The price: during the in-flight window the text stays in the box, which is correct and
  matches the disabled state.
- "Pending bubble" vs "keep it in the box": the design draws a bubble with retry/discard, which needs
  Alpine state (CSP-registered component, listening to `htmx:sendError`/`htmx:responseError`) holding
  `{key, body, status}`. Retry re-sends the same body with the same key; discard drops it and restores
  nothing. Keep this a small Alpine component, not a hand-rolled fetch layer. (The page-level
  `htmx:beforeSwap` handler in `base/static/base/js/alpine-components.js` already shows the project's
  place for global error-swap rules.)
- Multiple unsent messages: key-per-bubble; a successful poll that returns a message with that key replaces
  the pending bubble (prototype `pending.filter(!keys.has(p.key))`). Needs the key rendered into each
  message `<li data-client-key>` only for the sender's own messages.

### Policy refusal: 422 with the reason
- FLS convention (CLAUDE.md, `htmx` skill): **422 for validation/refusal on HTMX requests**, with a re-rendered
  fragment; `base/static/base/js/alpine-components.js` already lets htmx swap 422 bodies
  (`htmx:beforeSwap` -> `shouldSwap = true`). `comms/messaging_policy.py` returns an object whose `.allowed`
  must be read (comment: "Force callers to read .allowed"), carrying the reason.
- A refusal returns 422 with a fragment that **replaces the composer** (`outerHTML`) with the reason text
  and either the composer disabled / replaced ("replies closed" state, design 03 D) or kept with an inline
  `role="alert"` message (design 03 C: "policy changed after the thread opened"). Keep the typed text in the
  textarea or the bubble so nothing is lost; a refusal is not a network failure and must not offer a blind
  "Retry" that will keep failing: show the reason and (for permanent closure) Discard only. The prototype
  already separates `"failed"` (retry) from `"refused"` (no retry).
- Keep the 422 reason server-rendered (the policy owns the copy). Do not mix a policy refusal with the
  idempotency path: a key that already created a message returns 200 (above), so a refused key never
  created anything and a later retry after policy re-opens is simply a new first send.
- Also return 422 for the ordinary empty/too-long body (character counter in the design) on the same path.
- Auth expiry: `login_required_htmx` 204 + `HX-Redirect`; a draft would be lost on the full navigation.
  Mitigation to consider: a site-wide, per-thread `localStorage` draft is out of scope; mention only.

## 4. Server load

- **Cost model.** Each poll is one authenticated GET (session + auth middleware, same stack the bell pays) plus
  one indexed query. N open threads means N timers, but only threads whose tab is **visible** poll (hidden
  tabs stop, per the visibility idiom), so for a typical user the active cost is one thread poll plus one
  badge poll at a time, not N. Two panes on desktop: one thread + one inbox. The bell's 45s plus a thread's
  5-10s is on the order of 7-14 requests/min/active visible tab; multiply by concurrently open viewers, which
  is bounded by simultaneous *active* conversations, not by registered users.
- **Indexes.** `Message` needs `Index(fields=["conversation", "created_at", "id"])` (matching the keyset
  order: forward `after` scan and backward `before` scan both walk it, `Index` is bidirectional; add `-id`
  variants only if the planner wants them). That makes "anything newer than cursor?" an index range scan that
  touches zero heap pages when nothing is new, and "page before cursor" an index scan with `LIMIT`. Follow
  the existing comms pattern (`Notification`: `Index(user, site, -created_at)` plus a partial index
  `comms_notification_unseen_idx` with `condition=Q(read_at__isnull=True, seen_at__isnull=True)`): add a
  partial index for unread (`recipient`/`conversation` where `read_at IS NULL`) to serve the inbox unread count
  and the header Messages count.
  Site scoping: `SiteAwareManager` filters by the current site inside a request; keep it as the default so
  poll queries need no extra predicates, but confirm `site` is covered where the planner needs it.
- **Conversation-level checkpoint.** Store `last_message_at` (and last sender) on the conversation, updated in
  the same transaction as the message insert. The inbox "anything new?" check is then
  `Conversation.objects.filter(participant=user, last_message_at__gt=since).exists()` on a small table,
  rather than scanning messages. The thread poll can use the same value as a **pre-check**: send
  `?after=...&seen=<conversation.last_message_at>` and answer 204 with one primary-key lookup before touching
  `Message`. This is the cheapest "anything new?" and it is also exactly where the policy state
  (read-only/closed) can be returned.
- **No caching** (production cache is DB-backed: a cache read costs a DB round trip and adds invalidation).
  An `ETag`/`If-None-Match` or `If-Modified-Since` for the 204 path is possible but htmx's 204 is simpler and
  already matches FLS practice.
- **Backoff and limits.** If messages are sent in the open thread, a freshly sent message resets the poll to the
  fast cadence; an idle thread may relax (e.g. 5s -> 15s -> 30s after minutes without activity) and snap back
  on `visibilitychange`/focus. That is optional tuning; the first version can poll flat.
- **Rate limiting** the send endpoint is a separate abuse topic (Axes is installed for logins only); mention
  only to the policy spec.
- **Scaling limit.** Polling is right for this scale and matches FLS (no websocket/Channels/Redis in the
  stack; the cache is DB-backed). If concurrent live threads grow to where the interval is the bottleneck, the
  upgrade path is SSE via the htmx SSE extension or Channels, not shorter intervals. Out of scope here.

## Recommendations (summary)

1. Reuse the bell's visibility-aware Alpine timer + custom event idiom for thread and inbox polls; do not
   use an inline-filtered `hx-trigger="every"` (CSP). Thread ~5-10s, inbox ~30-45s, both settings.
2. Thread poll: `GET ?after=<created_at>_<id>`, 204 when nothing, else only new `<li>` with
   `hx-swap="beforeend"`; apply `login_required_htmx`; 286 is irrelevant to an Alpine-driven timer.
3. Keyset cursors on `(created_at, id)`: UUID4 PKs make `id__lt` wrong. Cursors live in the DOM and only move
   outward; "load earlier" is a button with `afterbegin`/`outerHTML` swap and a `PAGE_SIZE+1` look-ahead.
4. Own-message duplicate: POST response moves the newer cursor; poll also uses a small overlap window with
   DOM dedupe by id; pending bubble replaced by `client_key`.
5. Scroll: record at-bottom before the swap; stick or show Alpine "new messages" pill; compensate
   `scrollTop` by the height delta on prepend; do not trust scroll anchoring.
6. Accessibility: a separate hidden `role="status"` region; announce "N new messages from <name>" only for
   incoming poll results; `role="alert"` for send failures and refusals; no `aria-live` on the list.
7. Sending: hidden per-draft UUID `client_key` with a partial unique constraint
   `(conversation, sender, client_key)` and a return-the-original-on-conflict path, **plus**
   `hx-disabled-elt` on the submit button. Clear the draft only on a successful swap. Policy refusal returns
   422 with the server-rendered reason and no Retry; transport failures (`htmx:sendError`) keep the draft with
   Retry/Discard.
8. Load: index `(conversation, created_at, id)` plus a partial unread index; keep
   `last_message_at` on the conversation as the O(1) "anything new?" pre-check; no cache; polling is paused for
   hidden tabs, so N open threads cost roughly one visible poll per user.

## Open questions for the spec
- Exact polling intervals and whether the thread poll shares the bell timer component or gets its own.
- Overlap window size for the timestamp cursor (2s suggested) vs a sequence column.
- Whether to announce the sender name (privacy on shared screens is the only argument against).
- Whether the unsent-draft bubble holds text only in memory (lost on reload) or the textarea alone suffices.

## Reference URLs
- htmx `hx-trigger` (`every`, filters, `from:`): https://htmx.org/attributes/hx-trigger/
- htmx polling and 286 "stop polling": https://htmx.org/docs/#polling
- htmx `hx-swap` (`beforeend`, `afterbegin`, `outerHTML`): https://htmx.org/attributes/hx-swap/
- htmx `hx-sync` (request coordination): https://htmx.org/attributes/hx-sync/
- htmx `hx-disabled-elt`: https://htmx.org/attributes/hx-disabled-elt/
- htmx events (`htmx:sendError`, `htmx:afterSettle`, `htmx:beforeSwap`): https://htmx.org/events/
- htmx 204 No Content does not swap: https://htmx.org/docs/#requests
- WCAG 2.2, 4.1.3 Status Messages: https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- MDN `aria-live` / live regions: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/ARIA_Live_Regions
- MDN CSS scroll anchoring (`overflow-anchor`): https://developer.mozilla.org/en-US/docs/Web/CSS/overflow-anchor
- Stripe idempotent requests (key pattern): https://docs.stripe.com/api/idempotent_requests
- Django `UniqueConstraint` with `condition`: https://docs.djangoproject.com/en/6.0/ref/models/constraints/#uniqueconstraint
- Django indexes: https://docs.djangoproject.com/en/6.0/ref/models/indexes/

Note: the web references above are standard documentation pages cited from knowledge; they were not
re-fetched in this run. FLS file facts (bell timer, `login_required_htmx`, UUID pks, 422 handler,
`hx-disabled-elt` usages, `comms` indexes) were read from the repo.

status: ok
