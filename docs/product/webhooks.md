# Webhooks

_Last updated: 2026-08-29_

## Summary

- FLS fires outbound webhooks on three events: user registration, course registration, and course completion. Each delivery carries a signed, tamper-detectable envelope.
- Endpoints authenticate either by HMAC signature in the [Standard Webhooks](https://www.standardwebhooks.com/) format, or through headers the integrator templates themselves.
- Per-site secrets are encrypted at rest. `WEBHOOK_ENCRYPTION_SALT` is required in production and the application refuses to start without it.
- Outbound URLs are SSRF-checked in production: HTTPS only, and no private, loopback, or link-local addresses.
- Failed deliveries retry with exponential back-off, and an endpoint that keeps failing is auto-disabled.
- Endpoints are configured in the Django admin. There is no webhook UI outside the admin.

## Events and Data Leaving the System

Webhooks are an outbound data flow to third-party systems. Three events ship by default:

- **User registration.** A new user completes email verification.
- **Course registration.** A learner self-registers, or is registered, for a course.
- **Course completion.** A learner completes every item in a course.

Each delivery is an envelope carrying a unique event id, the event type, a UTC timestamp, and the details of what happened: who the learner is, and for the course events, which course.

The course events also name the [organisation](./multi-tenancy-and-isolation.md#organisations) the learner is studying through, and identify which pass through the course the event concerns, so a receiver can pair a registration with the completion that follows it. A learner registered for the same course through two organisations produces two independent pairs.

Receivers should key on the envelope id for their own idempotency.

The event list is a registry a deployment can extend, not a fixed set.

Endpoints are site-scoped: one configured on site A only ever receives site A's events. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Authentication and Signing

Two modes are available per endpoint.

**HMAC signing (the default).** FLS signs each delivery with a random per-endpoint secret generated at creation, and sends the signature and its timestamp as headers in the [Standard Webhooks](https://www.standardwebhooks.com/) format. Receivers can verify it with any conforming library.

**Custom auth via headers.** FLS omits the signing headers and authentication happens entirely through the header template, injecting a static API key held in a webhook secret, for example. This mode requires a body template.

## Body and Header Templates

An endpoint can define Jinja2 templates for its request body and headers, so the outbound payload can be reshaped into whatever the receiving system expects: a transactional email API, a chat webhook, and so on. Templates can read the event envelope and the site's stored secrets.

The admin validates a template when the endpoint is saved, so a broken template fails in front of the administrator rather than silently at delivery time. Without a body template, the delivery sends the standard envelope unchanged.

## Secrets

Named secret values, such as API keys, can be stored per site and referenced from body and header templates. A secret on site A is not readable from site B. Values are encrypted at rest, and rotating the deployment's keys does not strand secrets written under an old one.

`WEBHOOK_ENCRYPTION_SALT` is **required in production**. The application fails at startup if it is unset, rather than falling back to the development default. These are the only application-level encrypted values in FLS; see [security and data handling](./security-and-data-handling.md#encryption-at-rest).

## SSRF Protection

In production, FLS checks an endpoint URL when it is saved: the scheme must be HTTPS, and the host must not resolve to a private, loopback, or link-local address. This stops the application being used as a proxy into internal network services.

**Known limitation.** The check happens when the endpoint is saved, but the host is resolved again when a delivery is sent. An attacker controlling DNS could answer with a public address at save time and a private one at delivery, bypassing the check. The fix is understood and not yet implemented.

## Delivery, Retries, and the Circuit Breaker

FLS records every attempt with its outcome, timing, and what the receiver said, so a failing integration can be diagnosed from the admin. That history outlives the endpoint: deleting an endpoint leaves its delivery records in place, each still naming the URL the send was aimed at.

**Retries.** Server errors, timeouts, and transport failures are retried with exponential back-off, then given up on. A rejection the receiver will never accept is not retried.

**Circuit breaker.** After repeated consecutive failures an endpoint is auto-disabled for a cooldown period, protecting the downstream system from a retry storm. A successful delivery clears the failure state. This is separate from the manual enable/disable toggle an administrator controls.

**Delivery is at most once per event per endpoint.** Dispatch runs on a background worker that may run a job more than once, but a repeated job will not send the same event to the same endpoint twice. Manual retries and admin test sends are separate records and are unaffected. One residual gap: a delivery left mid-flight by a worker crash is not picked up again automatically and needs a manual retry from the admin. See [deployment](./deployment.md) for the background-task worker.

## Admin Controls

From the Django admin an administrator can create and configure endpoints, manage secrets (values are not shown in plaintext after creation), review event and delivery records read-only, retry a failed delivery, and fire a **test send** to check an endpoint is reachable and its authentication correct before a live event triggers delivery.
