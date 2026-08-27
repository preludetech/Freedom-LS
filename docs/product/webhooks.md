# Webhooks

_Last updated: 2026-08-27_

## Summary

- FLS fires outbound webhooks on three events: user registration, course registration, and course completion. Each delivery carries a signed, tamper-detectable envelope.
- Endpoints support HMAC-SHA256 signing in the Standard Webhooks format, or custom authentication via templated headers.
- Per-site secrets are encrypted at rest. `WEBHOOK_ENCRYPTION_SALT` is required in production and the application refuses to start without it.
- Outbound URLs are SSRF-checked in production: HTTPS only, and no private, loopback, or link-local addresses.
- Failed deliveries retry with exponential back-off, and an endpoint that keeps failing is auto-disabled.
- Endpoints are configured in the Django admin. There is no webhook UI outside the admin.

## Events and Data Leaving the System

Webhooks are an outbound data flow to third-party systems. Three event types ship by default:

| Event type | Trigger | Payload fields |
|---|---|---|
| `user.registered` | New user completes email verification | `user_id`, `user_email`, `first_name`, `last_name` |
| `course.registered` | Learner self-registers or is registered for a course | `user_id`, `user_email`, `course_id`, `course_title`, `registered_at`, `organisation_id`, `course_progress_id` |
| `course.completed` | Learner completes every item in a course | `user_id`, `user_email`, `course_id`, `course_title`, `completed_time`, `organisation_id`, `course_progress_id` |

Every payload is wrapped in an envelope carrying the event's unique id, its type, an ISO 8601 UTC timestamp, and the event-specific fields above. Receivers should key on the envelope id for their own idempotency.

On the two course events, `organisation_id` names the [organisation](./multi-tenancy-and-isolation.md#organisations) the learner is studying through and `course_progress_id` identifies the progress record the event concerns, so a receiver can pair a registration event with the completion event for the same pass through a course. A learner registered for one course through two organisations produces two independent pairs.

The event list is a registry a deployment can extend, not a fixed set.

Endpoints are site-scoped: one configured on site A only ever receives site A's events. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Authentication and Signing

Two modes are available per endpoint.

**HMAC signing (the default).** Each delivery carries `webhook-id`, `webhook-timestamp`, and `webhook-signature` headers. The signature is an HMAC-SHA256 over `{webhook-id}.{webhook-timestamp}.{body}`, prefixed `v1,` and base64-encoded, using a random per-endpoint secret generated at creation. This is the [Standard Webhooks](https://www.standardwebhooks.com/) signature format, so receivers can verify with any conforming library.

**Custom auth via headers.** Signing headers are omitted and authentication is handled entirely through the header template — for example injecting a static API key held in a webhook secret. This mode requires a body template to be set.

## Body and Header Templates

An endpoint can define Jinja2 templates for its request body and headers, so the outbound payload can be reshaped into whatever the receiving system expects — a transactional email API, a chat webhook, and so on. Templates can read the event envelope and the site's stored secrets.

Templates are checked when an endpoint is saved through the admin: the Jinja syntax must parse, every secret referenced must exist, a JSON body must render to valid JSON, and headers must render to a JSON object. Without a body template, the delivery uses the standard envelope unchanged.

## Secrets

Named secret values (API keys and similar) can be stored per site and referenced from body and header templates. Values are encrypted at rest with Fernet symmetric encryption, using a key derived from the deployment's `SECRET_KEY` plus `WEBHOOK_ENCRYPTION_SALT`. Key rotation works through Django's secret-key fallback mechanism: old keys decrypt existing values while new writes use the current key.

`WEBHOOK_ENCRYPTION_SALT` is **required in production** — the application fails at startup if it is unset, rather than falling back to the development default. See [security and data handling](./security-and-data-handling.md).

Secrets are per site: a secret on site A is not readable from site B.

This is the only application-level encryption at rest in FLS. Database-level encryption is provider-dependent — see [security and data handling](./security-and-data-handling.md).

## SSRF Protection

In production, an endpoint URL is validated when it is saved: the scheme must be HTTPS, and the hostname is resolved with every returned address checked — if any is private, loopback, or link-local, the URL is rejected. This stops the application being used as a proxy into internal network services. Validation is skipped when running in debug mode so local endpoints can be tested.

**Known limitation.** The check resolves DNS at validation time, but the request re-resolves at delivery time. An attacker controlling DNS could return a public address during validation and a private one at delivery — a DNS rebinding bypass. The fix — pinning the resolved address for delivery — is known and not yet implemented.

## Delivery, Retries, and the Circuit Breaker

Every attempt is recorded with its status, attempt count, timing, response code, a truncated response body, and any transport error, so a failing integration can be diagnosed from the admin.

**Retries.** Server errors, timeouts, and transport failures are retried with exponential back-off — from one minute out to twelve hours, up to six attempts in total, with jitter. HTTP 429 responses honour the endpoint's `Retry-After` header. Other 4xx responses are treated as permanent failures and are not retried.

**Circuit breaker.** After repeated consecutive failures an endpoint is auto-disabled for a cooldown period, protecting the downstream system from a retry storm; a successful delivery clears the failure state. This is separate from the manual enable/disable toggle an administrator controls.

**Delivery is at most once per event per endpoint.** Webhook dispatch runs on a durable background worker with at-least-once execution, so a dispatch job can be redelivered — but a database constraint on the event-and-endpoint pair means a redelivered job does not send the webhook a second time. Manual retries and admin test sends are separate records and are unaffected. One residual gap: a delivery left mid-flight by a worker crash is not auto-retried and needs a manual retry from the admin. See [deployment](./deployment.md) for the background-task worker.

## Admin Controls

From the Django admin an administrator can create and configure endpoints (URL, event types, auth mode, templates), manage secrets (values are not shown in plaintext after creation), review event and delivery records read-only, retry a failed delivery, and fire a **test send** to check an endpoint is reachable and its authentication is correct before a live event triggers delivery.
