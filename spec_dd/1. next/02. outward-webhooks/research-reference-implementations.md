# Outbound Webhooks: Reference Implementations Research

## 1. Stripe Webhooks

### Configuration
- Endpoint URL (HTTPS required), optional description
- Select specific API version for event payloads
- Filter by event types at registration time (subscribe only to events you care about)
- Each endpoint gets a unique signing secret (`whsec_...`)

### Event Types & Filtering
- Dot-notation naming: `object.action` (e.g., `payment_intent.succeeded`, `invoice.paid`, `customer.subscription.updated`)
- Hundreds of event types across all Stripe resources
- Consumers choose which event types each endpoint receives

### Payload Structure
```json
{
  "id": "evt_1ABC...",
  "object": "event",
  "api_version": "2024-11-20",
  "created": 1732800000,
  "type": "payment_intent.succeeded",
  "data": {
    "object": { ... }
  }
}
```
- Envelope wraps the affected resource in `data.object`
- `type` field enables routing on the consumer side

### Signature / Security
- HMAC-SHA256 using endpoint-specific secret
- `Stripe-Signature` header contains timestamp `t` and signature `v1`
- Signed content = `timestamp.payload` (raw body)
- Timestamp included to prevent replay attacks

### Retry Policy
- **Live mode:** retries over 3 days with exponential backoff
- **Sandbox:** 3 retries over a few hours
- Success = any 2xx response; must respond quickly (before complex processing)
- Idempotency: consumers must handle duplicate delivery (same `evt_` id)

### Delivery Monitoring
- Workbench UI shows delivery status, timestamps, next retry time
- Can inspect payloads and response codes per delivery attempt

**Refs:**
- https://docs.stripe.com/webhooks
- https://docs.stripe.com/webhooks/signature
- https://docs.stripe.com/workbench/event-destinations

---

## 2. GitHub Webhooks

### Configuration
- Endpoint URL, shared secret for signing, content type (`application/json` or `application/x-www-form-urlencoded`)
- Can be configured at repository or organization level
- Up to 20 endpoints per event per installation target

### Event Types & Filtering
- 73+ event types: `push`, `pull_request`, `issues`, `release`, `workflow_run`, etc.
- Subscribe to specific events per webhook endpoint
- Can also subscribe to `*` (all events)

### Payload Structure
- JSON body with event-specific fields
- Key headers:
  - `X-GitHub-Event`: event type name
  - `X-GitHub-Delivery`: unique GUID (use as idempotency key)
  - `X-Hub-Signature-256`: HMAC-SHA256 signature (`sha256=...`)
- Payload shape varies by event type but always includes `action`, `sender`, and the relevant resource

### Signature / Security
- HMAC-SHA256 using shared secret
- Signature in `X-Hub-Signature-256` header (legacy: `X-Hub-Signature` with SHA1)
- Must use constant-time comparison to prevent timing attacks

### Retry Policy
- **No automatic retries.** If delivery fails, it is not retried.
- Manual redeliver button available in the UI
- 10-second timeout; must respond with 2xx within that window

### Delivery Monitoring
- Excellent built-in UI: last 30 days of deliveries
- Shows event trigger, timestamp, status code, full request/response
- Manual "Redeliver" button per delivery

**Refs:**
- https://docs.github.com/en/webhooks
- https://docs.github.com/en/webhooks/webhook-events-and-payloads
- https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries

---

## 3. Slack (Events API)

*Note: Slack's "Outgoing Webhooks" are a deprecated legacy feature. The modern equivalent is the Events API.*

### Configuration
- Register a Request URL in the app settings
- URL must pass a verification challenge (Slack sends a `challenge` parameter, your server echoes it back)
- Subscribe to specific event types (bot events vs. user events)

### Event Types & Filtering
- Workspace events: `message`, `app_mention`, `reaction_added`, `member_joined_channel`, etc.
- Subscribe per-app; endpoint receives only subscribed event types
- Legacy outgoing webhooks used trigger words and channel filters

### Payload Structure
- JSON wrapper with event metadata:
  - `token`, `team_id`, `api_app_id`, `event` (the actual event data), `type`, `event_id`, `event_time`
- The `event` field contains type-specific data
- Retry headers indicate if delivery is a retry attempt

### Signature / Security
- HMAC-SHA256 using signing secret
- `X-Slack-Signature` header, `X-Slack-Request-Timestamp` header
- Signed content = `v0:timestamp:body`

### Retry Policy
- Must respond with 2xx within **3 seconds**
- 3 retries with exponential backoff on failure
- Optional "Delayed Events" feature: hourly retries for 24 hours after the initial 3 retries
- Can opt out of retries via response header

### Delivery Monitoring
- Limited compared to Stripe/GitHub
- App dashboard shows some event delivery status

**Refs:**
- https://docs.slack.dev/apis/events-api/
- https://api.slack.com/events
- https://api.slack.com/legacy/custom-integrations/outgoing-webhooks

---

## 4. Svix (Webhook Infrastructure Provider)

Svix is purpose-built infrastructure for sending webhooks. It is relevant both as a reference architecture and as a potential dependency.

### Configuration
- **Applications**: logical grouping (typically one per tenant/customer)
- **Endpoints**: URL + optional event type filter + optional rate limit + optional channels
- **Event types**: registered centrally, endpoints subscribe to a subset (default: all)
- Supports payload transformations (JavaScript functions to reshape payloads per endpoint)
- Endpoint secrets auto-generated or manually set

### Event Types & Filtering
- Free-form string identifiers: `user.signup`, `invoice.paid`, etc.
- Can define JSON schemas for event types (used for documentation and validation)
- Supports OpenAPI spec import to auto-create event types
- Endpoints can filter by event type and/or by channel

### Payload Structure
- Headers: `svix-id` (idempotency key), `svix-timestamp`, `svix-signature`
- Body is your custom JSON payload; Svix does not impose envelope structure
- Signed content = `svix_id.svix_timestamp.body`

### Signature / Security
- **Default:** HMAC-SHA256 with base64-encoded per-endpoint secret (prefixed `whsec_`)
- **Optional:** Ed25519 asymmetric signatures
- Signs: id + timestamp + body (prevents replay and tampering)
- Symmetric is recommended (~50x faster signing, ~160x faster verification)

### Retry Policy
- Exponential backoff with jitter: immediately, 5s, 5min, 30min, 2h, 5h, 10h, 10h
- Success = 2xx within 15 seconds; 3xx redirects count as failure
- If all attempts fail for 5 days, endpoint is auto-disabled and an `EndpointDisabledEvent` operational webhook fires
- Disable clock starts after multiple failures within 24h, with 12h+ between first and last

### Delivery Monitoring
- Full delivery logs with request/response details
- Management dashboard (embeddable in your product via pre-built UI components)
- Operational webhooks for system events (endpoint disabled, etc.)

### Self-hosted Option
- Open source server written in Rust: https://github.com/svix/svix-webhooks
- Can be self-hosted with PostgreSQL or Redis backend
- Docker deployment available

**Refs:**
- https://docs.svix.com/retries
- https://docs.svix.com/event-types
- https://docs.svix.com/security
- https://docs.svix.com/receiving/verifying-payloads/how-manual
- https://github.com/svix/svix-webhooks

---

## 5. Django-Specific Libraries

### svix-python
- Official Python SDK for the Svix API
- `pip install svix` / `uv add svix`
- Handles all webhook sending, signing, retry, and monitoring via the Svix service
- Can be used with self-hosted Svix server or Svix cloud
- Best choice if you want a fully managed webhook delivery pipeline
- Ref: https://www.svix.com/guides/sending/send-webhooks-with-python-django/

### django-webhook
- Plug-and-play Django app for outbound webhooks on model changes
- Uses Django signals + Celery for async delivery
- Automatically triggers on model create/update/delete
- Simple but limited: tightly coupled to model signals, less control over event types
- Ref: https://github.com/danihodovic/django-webhook, https://django-webhook.readthedocs.io/

### django-rest-hooks (Zapier)
- Hooks into Django signals and DRF serializers
- Consumers register webhooks via REST API
- More mature but less actively maintained
- Ref: https://github.com/zapier/django-rest-hooks

### Roll Your Own
- Many teams build custom webhook systems since the core is straightforward:
  - Model for webhook subscriptions (URL, secret, event types)
  - Celery/background task for delivery with retry
  - HMAC signing
  - Delivery log model
- This is the most common approach for LMS-scale systems that need full control

---

## Key Patterns Summary

| Aspect | Stripe | GitHub | Slack | Svix |
|---|---|---|---|---|
| **Signing** | HMAC-SHA256 | HMAC-SHA256 | HMAC-SHA256 | HMAC-SHA256 (default) or Ed25519 |
| **Event naming** | `object.action` | flat names | flat names | free-form (recommend `object.action`) |
| **Retry strategy** | 3 days, exp backoff | None (manual redeliver) | 3 retries + optional 24h hourly | 8 attempts over ~33h, exp backoff + jitter |
| **Timeout** | Not specified (fast) | 10 seconds | 3 seconds | 15 seconds |
| **Delivery logs** | Yes (Workbench) | Yes (30 days, excellent UI) | Limited | Yes (full logs + dashboard) |
| **Idempotency key** | `evt_` id | `X-GitHub-Delivery` | `event_id` | `svix-id` header |
| **Endpoint disable** | Not automatic | N/A | N/A | Auto after 5 days of failures |
