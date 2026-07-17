# Webhooks

_Last updated: 2026-07-17_

## Summary

- Freedom LS fires outbound webhooks on three events: user registration, course completion, and course registration. Each delivery carries a signed, tamper-detectable envelope.
- Webhook endpoints support HMAC-SHA256 signing (Standard Webhooks format) or custom authentication via templated headers.
- Per-site webhook secrets are encrypted at rest using Fernet symmetric encryption (`django-fernet-encrypted-fields`). The encryption key is derived from `SECRET_KEY` plus a configurable salt (`WEBHOOK_ENCRYPTION_SALT`).
- SSRF protection is enforced in production: webhook URLs must use HTTPS and must not resolve to private, loopback, or link-local IP addresses.
- Failed deliveries are retried with exponential back-off (up to 5 retries); a circuit breaker auto-disables an endpoint after repeated failures to protect downstream systems.

## Events and Data Leaving the System

Webhooks represent an outbound data flow to third-party systems. The following events are supported:

| Event type | Trigger | Payload fields |
|---|---|---|
| `user.registered` | New user completes email verification | `user_id`, `user_email`, `first_name`, `last_name` |
| `course.completed` | Learner's `CourseProgress` transitions to complete | `user_id`, `user_email`, `course_id`, `course_title`, `completed_time` |
| `course.registered` | Learner self-registers or is registered for a course | `user_id`, `user_email`, `course_id`, `course_title`, `registered_at` |

All payloads are wrapped in an envelope with: `id` (event UUID), `type`, `timestamp` (ISO 8601 UTC), `data` (event-specific fields above).

Webhook endpoints are site-scoped (see [multi-tenancy and isolation](./multi-tenancy-and-isolation.md)): an endpoint configured on site A only receives events from site A.

## Authentication and Signing

Two authentication modes are available per endpoint (`auth_type` field on `WebhookEndpoint`):

**HMAC signing (`signing`, the default).** Every delivery includes three headers:
- `webhook-id` — the event UUID
- `webhook-timestamp` — Unix timestamp of delivery
- `webhook-signature` — `v1,<base64-encoded HMAC-SHA256>`

The HMAC is computed over the string `{webhook-id}.{webhook-timestamp}.{body}` using the endpoint's secret (a 48-byte URL-safe random token generated at endpoint creation). This follows the Standard Webhooks signature format, allowing receivers to verify that the payload has not been tampered with and was sent by this server.

**Custom auth via headers (`none`).** The `auth_type` can be set to `none`, in which case HMAC headers are not added. Authentication is then handled entirely through the Jinja2 headers template (e.g., inject a static API key from a webhook secret). This mode requires a `body_template` to be set.

## Webhook Secrets (Encrypted at Rest)

`WebhookSecret` records store named string values (e.g., API keys for third-party services) that can be referenced in body and header templates as `{{ secrets.my_key_name }}`. Secret values are stored using `EncryptedTextField` from `django-fernet-encrypted-fields`, which applies Fernet symmetric encryption before writing to the database.

The encryption key is derived from Django's `SECRET_KEY` plus `SALT_KEY` (set from the `WEBHOOK_ENCRYPTION_SALT` environment variable in production) using PBKDF2. Key rotation is supported by Django's `SECRET_KEY_FALLBACKS` mechanism: old keys can decrypt existing ciphertext while new encryption uses the current key.

Secrets are per-site: `WebhookSecret` has a `unique_together` constraint on `(site, name)`. A secret created on site A is not accessible to site B.

This is the only application-level encryption at rest in Freedom LS. General database-level encryption at rest is provider-dependent and not provided by the application layer.

## Body and Header Templates (Jinja2)

Endpoints can optionally define a `body_template` and `headers_template` as Jinja2 strings. This allows the outbound payload to be transformed into the format expected by the receiving system (e.g., a Brevo transactional email API, a Slack webhook).

Template context variables: `event` (the event envelope dict) and `secrets` (a dict of all `WebhookSecret` values for this site, keyed by name).

Templates are validated at save time:
- Jinja2 syntax is checked.
- All `secrets.*` references must correspond to existing `WebhookSecret` records.
- If `content_type` is `application/json`, the rendered body is parsed as JSON and rejected if invalid.
- `headers_template` must render to a JSON object.

If `body_template` is not set, the delivery uses the standard JSON envelope without transformation.

## SSRF Protection

In production (`settings.DEBUG = False`), every `WebhookEndpoint` URL is validated when the endpoint is saved (`clean()` method calls `_validate_url_ssrf()`):

1. The URL scheme must be `https`. HTTP URLs are rejected.
2. The hostname is resolved via `socket.getaddrinfo()`. All resolved IP addresses are checked; if any address is private, loopback, or link-local, the URL is rejected.

This prevents the application from being used as a proxy to make requests to internal network services.

**Known limitation.** The SSRF check resolves DNS at validation time. A DNS rebinding attack (an attacker returning a public IP during validation and a private IP at delivery time) could bypass this check. A TODO in `freedom_ls/webhooks/models.py` documents this and describes the fix (pinning the resolved IP for use at delivery time). This has not yet been implemented.

SSRF validation is skipped in development (`DEBUG = True`) to allow local testing endpoints.

## Retry and Circuit Breaker

**Retry schedule.** On non-2xx responses (5xx, timeout, transport error), the delivery is re-queued. Retry delays in seconds: 60, 300, 1800, 7200, 43200 (1 min → 5 min → 30 min → 2 hr → 12 hr). Maximum 6 total attempts (1 initial + 5 retries). HTTP 429 responses honour the `Retry-After` header.

HTTP 4xx responses (other than 429) are treated as permanent failures and are not retried.

**Circuit breaker.** `WebhookEndpoint` tracks a `failure_count` and a `disabled_at` timestamp. When the failure count reaches `CIRCUIT_BREAKER_THRESHOLD = 5`, the endpoint is auto-disabled (`disabled_at` is set). The circuit breaker cooldown is 1 hour; after the cooldown, deliveries can be attempted again. Successful delivery resets `failure_count` and clears `disabled_at`.

The `is_active` flag on an endpoint is the admin's explicit enable/disable toggle; it is separate from the circuit breaker state.

## Delivery Records

Each delivery attempt is recorded as a `WebhookDelivery` row containing:

- `status` — `pending`, `success`, `failed`, `permanent_failure`, `dead_letter`
- `attempt_count`, `next_retry_at`, `last_attempt_at`
- `last_status_code`, `last_response_body` (truncated to 500 characters), `last_latency_ms`
- `last_response_error_message`

`WebhookDelivery` records are read-only in the admin, with a manual retry action available.

A given event is delivered to a given endpoint at most once. In production, webhook dispatch runs on a durable background worker that guarantees at-least-once execution, so the dispatch job can be redelivered; the delivery is idempotent per event-and-endpoint, so a redelivered job does not send the webhook a second time. Manual retries and the admin test-send action operate on their own delivery records and are unaffected. See [deployment](./deployment.md) for the background-task backend.

## Admin Controls

From the Django admin:

- Create and configure `WebhookEndpoint` records (URL, event types, auth mode, templates).
- Create and manage `WebhookSecret` records (encrypted values not shown in plaintext after creation).
- View `WebhookEvent` and `WebhookDelivery` records (read-only).
- **Test-send action** on a `WebhookEndpoint` admin detail page — fires a test delivery using sample event data.
- Retry action on failed `WebhookDelivery` records.
