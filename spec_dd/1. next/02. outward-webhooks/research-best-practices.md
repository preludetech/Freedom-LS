# Outward Webhooks: Best Practices Research

## 1. Standard Webhook Payload Format

The [Standard Webhooks specification](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md) defines a common set of conventions adopted by providers like Stripe, GitHub, and Svix.

**Typical payload fields:**

```json
{
  "id": "evt_1234567890",
  "type": "student.progress.completed",
  "timestamp": "2026-03-09T12:00:00Z",
  "data": {
    "object_type": "topic_progress",
    "object_id": "abc-123",
    "...": "event-specific fields"
  },
  "api_version": "2026-03-01"
}
```

- **id** -- Unique, stable event identifier (used for idempotency and deduplication).
- **type** -- Dot-namespaced event type string (e.g. `resource.action`).
- **timestamp** -- ISO 8601 UTC timestamp of when the event occurred.
- **data** -- The actual event payload. Keep it small; include IDs and key fields, let consumers fetch full resources via API if needed.
- **api_version** -- Optional but recommended for forward compatibility.

Avoid including sensitive data (passwords, tokens, PII) in payloads. Include only what is necessary for the consumer to act on the event.

## 2. Security Best Practices

### HMAC Signing

Every outbound webhook must be signed. The industry standard is HMAC-SHA256:

1. Generate a unique secret per webhook subscription.
2. Concatenate: `{msg_id}.{timestamp}.{body}` (the Standard Webhooks convention).
3. Compute HMAC-SHA256 of the concatenated string using the shared secret.
4. Send the signature in a header.

**Standard headers (per Standard Webhooks spec):**

| Header | Value |
|---|---|
| `webhook-id` | Unique message ID (e.g. `msg_abc123`) |
| `webhook-timestamp` | Unix timestamp (seconds) of send time |
| `webhook-signature` | `v1,<base64-encoded-signature>` (space-delimited list for key rotation) |

### Additional Security Measures

- **HTTPS only** -- Never send webhooks over plain HTTP in production.
- **Timestamp validation** -- Include a timestamp; consumers should reject messages older than 5 minutes to prevent replay attacks.
- **Secret rotation** -- Support multiple active signatures (space-delimited in header) to allow zero-downtime secret rotation.
- **IP allowlisting** -- Optionally publish a list of source IPs that consumers can allowlist.

### References

- [Standard Webhooks Spec](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md)
- [HackerOne: Securely Signing Webhooks](https://www.hackerone.com/blog/securely-signing-webhooks-best-practices-your-application)
- [Webhook Security Best Practices 2025-2026](https://dev.to/digital_trubador/webhook-security-best-practices-for-production-2025-2026-384n)
- [Hooklistener: Webhook Security Fundamentals](https://www.hooklistener.com/learn/webhook-security-fundamentals)

## 3. Retry Strategies

### Exponential Backoff with Jitter

Failed deliveries should be retried using exponential backoff with random jitter to avoid thundering herd problems.

**Typical schedule:**

| Attempt | Base Delay | With Jitter (approx) |
|---|---|---|
| 1 | Immediate | 0s |
| 2 | 30s | 15-45s |
| 3 | 2 min | 1-3 min |
| 4 | 8 min | 4-12 min |
| 5 | 30 min | 15-45 min |
| 6 | 2 hours | 1-3 hours |
| 7+ | Capped at 4-6 hours | Until max window |

**Key parameters:**

- **Max retries**: 5-8 attempts is typical.
- **Max retry window**: 24-72 hours total from first attempt.
- **Delay cap**: Cap individual delays at 1-6 hours.
- **Jitter**: Full jitter (random between 0 and calculated delay) is recommended over equal jitter.

### Timeout Handling

- Set a **request timeout of 15-30 seconds** per delivery attempt.
- Connection timeout should be shorter (5-10 seconds).
- If the consumer does not respond within the timeout, treat it as a retriable failure.

### Response Classification

| Response | Action |
|---|---|
| 2xx | Success -- mark delivered |
| 4xx (except 429) | Permanent failure -- do not retry, send to DLQ |
| 429 | Rate limited -- honour `Retry-After` header, then retry |
| 5xx | Transient failure -- retry with backoff |
| Timeout / connection error | Transient failure -- retry with backoff |

### Dead Letter Queue (DLQ)

After exhausting retries, move events to a DLQ. Provide a UI or API for consumers to inspect and replay failed events.

### References

- [Hookdeck: Outbound Webhook Retry Best Practices](https://hookdeck.com/outpost/guides/outbound-webhook-retry-best-practices)
- [WebhookStream: Retry Strategies and Exponential Backoff](https://webhookstream.com/blog/webhook-retry-strategies-and-exponential-backoff-explained)
- [AWS: Retry with Backoff Pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html)

## 4. Delivery Tracking and Logging

### What to Log Per Delivery Attempt

- Event ID and type
- Subscription/endpoint URL (redacted if needed)
- HTTP status code returned
- Response body (first N bytes, for debugging)
- Request duration (latency)
- Attempt number
- Timestamp of attempt
- Success/failure status

### Metrics to Track

- **Delivery success rate** -- per endpoint, per event type (7-day and 28-day windows).
- **Latency buckets** -- time from event creation to successful delivery.
- **Retry rate** -- how often events need retries.
- **DLQ depth** -- number of events that exhausted all retries.
- **Duplicate delivery rate** -- idempotency cache hits.

### Consumer-Facing Features

- Provide a delivery log UI showing recent attempts, status codes, and response snippets.
- Allow manual replay of individual events or bulk replay from DLQ.
- Send notifications (email or in-app) when an endpoint is consistently failing.

### References

- [Hookdeck: Webhooks at Scale](https://hookdeck.com/blog/webhooks-at-scale)

## 5. HTTP Conventions

### Request Format

- **Method**: Always `POST`.
- **Content-Type**: `application/json` (standard; support `application/x-www-form-urlencoded` only if consumers require it).
- **User-Agent**: Include a custom user agent identifying your service (e.g. `FreedomLS-Webhooks/1.0`).

### Standard Headers

```
POST /webhook-endpoint HTTP/1.1
Content-Type: application/json
User-Agent: FreedomLS-Webhooks/1.0
webhook-id: msg_2xAuKbN7vmZJMrOzLQoN1FMObiU
webhook-timestamp: 1709971200
webhook-signature: v1,K5oZfzN95Z9UVu1EsfQnFnGMJIG1nHhOOWXUPSLpSIA=
```

### Success/Failure Status Codes (from consumer)

| Consumer Returns | Provider Interpretation |
|---|---|
| 200, 201, 202, 204 | Delivery successful |
| 410 Gone | Endpoint deactivated; disable the subscription |
| 429 | Rate limited; back off and retry |
| 4xx (other) | Permanent failure; do not retry |
| 5xx | Transient failure; retry |

### References

- [Prismatic: Anatomy of a Webhook HTTP Request](https://prismatic.io/blog/anatomy-webhook-http-request/)
- [webhooks.fyi: Best Practices for Webhook Providers](https://webhooks.fyi/best-practices/webhook-providers)
- [Hookdeck: Webhook Payload Best Practices](https://hookdeck.com/outpost/guides/webhook-payload-best-practices)

## 6. Idempotency Considerations

Webhook delivery is **at-least-once**, meaning consumers may receive the same event multiple times due to retries, network issues, or infrastructure failures.

### Provider Responsibilities

- **Include a stable event ID** (`webhook-id` / `id` in payload) that remains the same across retries of the same event.
- **Document idempotency expectations** -- tell consumers to deduplicate using the event ID.

### Consumer-Side (guidance to document for consumers)

- Maintain a `processed_webhooks` table with a unique constraint on event ID.
- Check for existing event ID before processing.
- Persist the event ID **before** performing side effects (e.g. sending emails).
- Use a TTL on stored event IDs (e.g. 7-30 days) to bound storage.

### Provider-Side Idempotency

- Use idempotent event generation: the same domain event should always produce the same event ID, even if the event creation is retried internally.
- Deduplication at the queue level (e.g. SQS deduplication ID) to prevent duplicate sends.

### References

- [Hookdeck: How to Implement Webhook Idempotency](https://hookdeck.com/webhooks/guides/implement-webhook-idempotency)
- [Shopify: Webhook Best Practices](https://shopify.dev/docs/apps/build/webhooks/best-practices)
- [Medium: Top 7 Webhook Reliability Tricks for Idempotency](https://medium.com/@kaushalsinh73/top-7-webhook-reliability-tricks-for-idempotency-a098f3ef5809)

## 7. Rate Limiting and Circuit Breaker Patterns

### Rate Limiting (Provider Side)

Protect consumer endpoints from being overwhelmed:

- **Per-endpoint rate limits**: Allow consumers to configure their max throughput (e.g. 100 req/s).
- **Default rate limit**: Apply a sensible default (e.g. 30 req/s) if not configured.
- **Honour 429 responses**: When a consumer returns 429, respect the `Retry-After` header and queue pending events.
- **Batch/aggregate events**: Where possible, allow consumers to opt into batched delivery to reduce request volume.

### Circuit Breaker Pattern

If an endpoint consistently fails, stop sending to avoid wasting resources and looking like a DDoS attack.

**Three states:**

1. **Closed (normal)** -- Requests flow normally. Monitor failure rate.
2. **Open (failing)** -- Stop all deliveries to the endpoint. Queue events for later. Trigger after a threshold (e.g. 5 consecutive failures, or >90% failure rate over 1 hour).
3. **Half-open (probing)** -- After a cooldown period (e.g. 5-10 minutes), send a single test event. If it succeeds, move back to Closed and flush queued events. If it fails, return to Open with a longer cooldown.

**Thresholds to consider:**

- Open after N consecutive failures (e.g. 5-10).
- Or open after failure rate exceeds X% over a time window.
- Cooldown period increases with repeated open/half-open cycles.
- After extended outage (e.g. 72 hours), disable the subscription and notify the consumer.

### References

- [Hookdeck: How We Built a Rate Limiter for Outbound Webhooks](https://hookdeck.com/blog/how-we-built-a-rate-limiter-for-outbound-webhooks)
- [Svix: Webhook Rate Limit](https://www.svix.com/resources/glossary/webhook-rate-limit/)
- [DZone: Retry Pattern With Exponential Back-Off and Circuit Breaker](https://dzone.com/articles/understanding-retry-pattern-with-exponential-back)
- [Inventive: Webhook Best Practices Guide](https://inventivehq.com/blog/webhook-best-practices-guide)
