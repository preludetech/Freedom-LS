# Outward Webhooks

We need to use webhooks to tell third-party services about different events on the platform. For example, when a new user signs up we might want to use a webhook to notify a transactional email provider so it can kick off a flow of emails.

## Core requirements

- Webhooks are site-aware: each site configures its own webhook endpoints independently
- One site can have multiple webhook endpoints pointing at different services
- Each endpoint subscribes to specific event types (e.g. `user.registered`, `progress.completed`)
- Webhook delivery is tracked so we can retry on failure
- Webhooks live in their own Django app (`webhooks`) with a utility function that other apps call to fire events

## Triggering

- Use custom Django signals to decouple event sources from the webhook system. Apps send signals (e.g. `webhook_event.send(event_type="user.registered", payload={...})`) and the webhooks app listens
- The webhooks app connects a signal receiver that handles looking up endpoints and queuing delivery
- This keeps event-producing apps independent of the webhook app — they just fire a signal
- Delivery is decoupled from the request/response cycle using `transaction.on_commit` + background tasks

## Task framework

- Use Django 6.0's built-in Tasks framework (`django.tasks`)
- Lightweight: database-backed worker, no Redis/RabbitMQ dependency

## Standards and security

- Follow the Standard Webhooks spec for interoperability (used by Stripe, Svix, etc.)
- Standard headers: `webhook-id`, `webhook-timestamp`, `webhook-signature`
- HMAC-SHA256 signing with a per-endpoint secret
- HTTPS only in production

## Retry and resilience

- Exponential backoff with jitter on failed deliveries
- Classify responses: 2xx = success, 5xx/timeout = retry, 4xx (except 429) = permanent failure
- Circuit breaker: auto-disable endpoints after sustained failures, probe periodically, re-enable on success
- Dead letter queue: after exhausting retries, events are stored for manual inspection and replay

## Delivery tracking

- Log every delivery attempt: event type, status code, response snippet, latency, attempt number
- Admin can inspect delivery history, manually retry failed deliveries, and send test pings

## Admin interface

- Managed through Django admin (Unfold) for now, may move to a dedicated UI later
- Configure endpoints: URL, event subscriptions, active/inactive toggle
- View delivery logs filtered by endpoint, event type, success/failure

## Payload format

- Follow the `resource.action` dot-notation convention for event types
- Envelope: `id`, `type`, `timestamp`, `data`
- Keep payloads small: include IDs and key fields, consumers fetch full resources via API if needed
- Never include sensitive data (passwords, tokens, PII) in payloads
