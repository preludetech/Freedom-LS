# Real-time updates over Django Channels

Spec 8 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An optional push transport, built on Django Channels, for two surfaces: the unread badge in the
header bar, and the conversation thread a user has open. With it switched on, a new notification
or message reaches an open page as soon as it is created instead of on the next poll. It is off by
default. Every install that runs no channel layer keeps the HTMX polling that the earlier specs
built, and nothing changes for it.

The spec also documents the deployment this needs: an ASGI server, a channel layer, and how the
two sit beside the WSGI process FLS deployments run today.

## Why

Polling is good enough for a badge, but a live conversation feels slow when the other person's
reply only arrives on the next poll. Some installs will want messages to arrive at once and can run
the extra infrastructure. Most FLS deployments cannot: the reference deployment is gunicorn on
WSGI, `config/asgi.py` is imported by nothing, and `docs/product/deployment.md` presents "no
Celery, Redis, or separate broker" as a feature. So push has to be something an install opts into,
and polling stays the path most installs use.

## What is settled

- **The transport is Django Channels over WebSockets.** It needs an ASGI server and a channel layer
  for fan-out across processes. The in-memory layer works only in a single process, so it does not
  count as a production setup.
- **Off by default, and polling is always the fallback.** An install with no channel layer
  configured opens no socket and behaves exactly as it did before this spec. When push is on and
  the socket fails to connect or drops, the page goes back to polling. No surface ever depends on
  a live connection.
- **Scope is the unread badge and open threads.** The badge covers unread notifications and unread
  conversations. Open threads are the learner thread page and the educator's views of a
  conversation: the inbox section and the message tab in the learner quick view. Everything else
  (the notification centre page, the inbox list, the report queue wherever spec 6 put it) keeps
  its current refresh behaviour.
- **A push never shows more than a poll would.** Whatever a push delivers passes the same checks
  as the poll that would otherwise have fetched it: the messaging policy, hidden messages, and
  blocks. A hidden message, or one from a user the recipient has blocked, is never pushed.
- **Sockets are per user and per site.** A connection belongs to one authenticated user on one
  site, and it only carries events for that user on that site. Code that runs outside a request,
  such as a consumer or the code that sends a push, passes `site_id` explicitly, because
  `SiteAwareManager` does not filter outside a request.
- **Pushed updates look and sound like polled ones.** The badge updates in the same `role="status"`
  live region, and new messages arrive in the same `role="log"` region. When the user has scrolled
  up in a thread, the same "new messages" prompt appears and the thread does not auto-scroll.
  Pushed updates get no new visual design.
- **The deployment story is documented as an opt-in.** The docs say what switching on push adds to
  a deployment: an ASGI server process, a channel layer backend, reverse-proxy routing for
  WebSocket upgrades, and health checks for both. They also say that a deployment which adds none
  of these keeps working on polling.

## Open until the spec

- What a push carries: rendered HTML fragments for the page to swap in, or a small "something
  changed" signal that makes the page run its existing poll right away. The second option reuses
  the poll endpoint's checks as they are.
- How an install switches push on, and how a page decides whether to open a socket or poll.
- Whether polling continues at a slower rate while the socket is connected, as a safety net for
  missed events.
- Whether `channels` becomes a core dependency or an optional extra, and which channel layer
  backends the docs recommend. Redis is the common choice, but a database-backed layer would keep
  the promise of no Redis.
- Whether the existing liveness and readiness probes grow a channel-layer check or leave it to the
  deployment.

## Out of scope

- Typing indicators, presence and live read receipts.
- Pushing to any surface other than the unread badge and open threads.
- Server-sent events or long polling as alternative transports.
- Making ASGI the default deployment, or changing the reference WSGI deployment for installs that
  do not opt in.

## Resources

- `user-communication/research_notification_sources_and_delivery.md`: section 3 covers the WSGI
  deployment today, the missing channel layer, and what Channels would cost a deployment.
- `user-communication/research_messaging_relationships_and_surfaces.md`: the header bar, the
  learner interface shell, the out-of-band toast machinery, and the educator quick view that
  pushed updates land in.
- `user-communication/research_comms_ux_pitfalls.md`: ARIA live regions for live unread counts,
  and missed-message pitfalls.
- `user-communication/research_comms_patterns.md` and `research_lms_comms_landscape.md`: how the
  in-app feed separates event creation from delivery, and how other LMSs handle live messaging.
- `user-communication-1-notifications-core/research_prior_notification_ux.md`: polling intervals,
  pausing polls in hidden tabs, the "new messages" banner, and announcing updates to screen readers.
- The specs this builds on: `user-communication-1-notifications-core` (badge and polling),
  `user-communication-4-direct-messaging` (threads), `user-communication-5-educator-messaging`
  (educator thread views), `user-communication-6-moderation` (hide and block).
- `spec_dd/3. done/2026-08-28_19:44_asgi-and-wsgi-name-a-settings-module-that-does-not-exist/`
  (the state of `config/asgi.py`) and `docs/product/deployment.md` (the deployment story to
  extend).
- Skills: `ds:htmx`, `fls-dev:multi-tenant`, `ds:app-settings`, `fls-dev:app-settings`,
  `fls-dev:testing`, `ds:playwright-tests`, `fls-dev:playwright-tests`, `domain-glossary`.
