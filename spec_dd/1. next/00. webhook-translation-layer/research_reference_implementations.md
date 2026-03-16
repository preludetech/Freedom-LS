# Research: Outbound Webhook Translation / Event Forwarding

## Problem Context

FLS needs to forward internal platform events (e.g. `user.registered`) to external APIs that each expect different payload formats, headers, and authentication. For example, notifying Brevo of a custom event requires calling a specific REST endpoint with a particular data structure, not a standard webhook receiver.

This document surveys how existing platforms solve outbound event routing, payload transformation, and secrets management.

---

## 1. Platforms That Do This Well

### 1.1 Svix (Webhook-as-a-Service)

Svix is purpose-built infrastructure for sending webhooks. It is open source (Rust server, PostgreSQL storage, optional Redis queue).

**Architecture:**
- API servers receive events, persist them, and enqueue them to a task queue
- Dispatch workers pull from the queue and deliver via outgoing proxies in an isolated VPC
- Supports multiple endpoints per customer with event-type-based fan-out
- Exponential backoff retries; HMAC-SHA256 payload signing

**Transformations:**
- Per-endpoint JavaScript transformation code via a `handler` function
- The handler receives an object with `method`, `url`, `payload`, `eventType`, and `cancel` properties
- `method`, `url`, `payload`, and `cancel` are mutable; `eventType` is read-only
- Custom `headers` can be returned to override endpoint defaults
- Setting `cancel = true` suppresses delivery silently

```javascript
function handler(webhook) {
  if (webhook.eventType === "invoice.created") {
    webhook.payload = {
      text: `An invoice of $${webhook.payload.amount} has been created.`
    };
  }
  return webhook;
}
```

**Transformation security sandbox:**
- No file system access, no environment variable reading, no network calls
- No async JavaScript operations allowed
- Hard resource limits prevent CPU/memory exhaustion attacks
- `transformationsParams` can be passed from the create-message API call (read-only in handler)

**Common transformation use cases (from Svix blog):**
1. URL path encoding - moving data from payload to URL path segments
2. Schema translation - restructuring payloads for third-party APIs
3. PII scrubbing - removing sensitive data before dispatch
4. Multi-format distribution - custom formatting for email, Slack, proprietary APIs

**Connectors (pre-built integrations):**
- Svix ships connectors for Slack, Discord, Teams, Hubspot, SendGrid, Zapier, etc.
- Each connector bundles transformation code, event type mappings, and auth flows
- Auth methods vary per connector: OAuth, API key entry, or manual webhook URL setup

**Transformation Templates:**
- Pre-written transformations that providers create for their customers
- Each template specifies: template type (predefined service or Custom), supported event types, and transformation code
- Templates serve as glue code turning incoming webhook events into useful payloads for specific integrations
- Svix also offers AI-generated templates via a "Generate with AI" button that knows about your event types and pre-built integrations

**Relevance to FLS:** The transformation handler pattern is directly applicable. Svix proves that a simple `handler(webhook) -> webhook` function signature is sufficient for most translation needs. The "Transformation Templates" concept (pre-built transformations for common integrations) is worth considering for FLS -- we could ship pre-built Jinja2 templates for common targets like Brevo, Slack, etc.

References:
- [Svix Webhook Architecture Diagram](https://www.svix.com/resources/webhook-architecture-diagram/)
- [Svix Transformations Docs](https://docs.svix.com/transformations)
- [Svix Connectors Docs](https://docs.svix.com/connectors)
- [Svix GitHub](https://github.com/svix/svix-webhooks)
- [Svix Blog: The What, Why, and How of Payload Transformations](https://www.svix.com/blog/transformations-feature/)
- [Svix Blog: Transformation Templates](https://www.svix.com/blog/introducing-transformation-templates/)

---

### 1.2 Hookdeck (Event Gateway)

Hookdeck is an event gateway that routes, transforms, and delivers webhooks at scale.

**Core concepts:**
- **Sources** - where events come from (webhook providers or internal systems)
- **Connections** - route events from a source to a destination, with optional rules
- **Destinations** - the target HTTP endpoints
- **Rules** - a pipeline of filters, transformations, and deduplication steps per connection

**Transformations:**
- Written in JavaScript (ES6) using an `addHandler` pattern
- Run in a V8 isolate sandbox (secure, parallel execution)
- 1-second execution limit, 5 MB code size max
- No IO operations, no async/await, no external resource access
- The handler receives `(request, context)` where request has `headers`, `body`, `query`, `path`

```javascript
addHandler("transform", (request, context) => {
  const { body, headers } = request;
  return {
    body: { event: body.action, email: body.user.email },
    headers: { ...headers, "X-Custom": "value" },
  };
});
```

**Secrets management:**
- Environment variables managed via the transformations editor UI
- Accessed as `process.env.VARIABLE_NAME` inside transformation code

**Relevance to FLS:** The sandboxed V8 approach is overkill for our needs, but the concept of a transformation function that receives and returns a request object (with body, headers) is a clean pattern. Their secrets-as-env-vars approach is simple and effective.

References:
- [Hookdeck Basics](https://hookdeck.com/docs/hookdeck-basics)
- [Hookdeck Transformations](https://hookdeck.com/docs/transformations)
- [Hookdeck Blog: Webhooks at Scale](https://hookdeck.com/blog/webhooks-at-scale)

---

### 1.3 Stripe (Outbound Webhooks from a SaaS Platform)

Stripe is the gold standard for outbound webhook design from an application platform.

**Event system:**
- 200+ event types following `resource.action` naming (e.g. `payment_intent.succeeded`)
- Customers subscribe specific endpoints to specific event types
- Each endpoint gets a unique signing secret

**Retry architecture:**
- Live mode: retries over 3 days with exponential backoff
- Test mode: 3 retries over a few hours
- Endpoints must respond 2xx within ~5 seconds
- Endpoints disabled after 3 days of failures, with email notification

**Payload signing:**
- HMAC-SHA256 signature in the `Stripe-Signature` header
- Includes a timestamp to prevent replay attacks
- Format: `t=timestamp,v1=signature`

**Key design choice:** Stripe does NOT offer payload transformation. Every consumer receives the same canonical JSON payload. This works because Stripe is the standard that others adapt to, not the other way around.

**Relevance to FLS:** We are not Stripe. Our consumers (Brevo, custom CRMs, etc.) each have their own API formats. We need transformation, which Stripe explicitly does not provide. However, Stripe's event naming convention (`resource.action`), signing approach, and retry strategy are best-in-class patterns to adopt.

References:
- [Stripe Webhooks Documentation](https://docs.stripe.com/webhooks)
- [Stripe Event Destinations](https://docs.stripe.com/workbench/event-destinations)
- [Svix Review of Stripe Webhooks](https://www.svix.com/resources/webhook-reviews/stripe-webhooks-review/)

---

### 1.4 Auth0 (Log Streams / Event Forwarding)

Auth0 forwards authentication events to external systems via "Log Streams."

**Architecture:**
- Events are auth-related (login, signup, failed attempts, etc.)
- Custom webhook streams send HTTP POST to a user-specified URL
- Payload format is JSON Lines (multiple log entries separated by newlines)
- One payload URL per webhook config, but the same URL can serve multiple streams

**Limitations:** No built-in transformation. The payload format is fixed. If the consumer expects a different format, you need middleware.

**Relevance to FLS:** Auth0 demonstrates the simplest viable approach (fixed payload, POST to URL) but also shows the pain point we are trying to solve: without transformation, every integration requires custom middleware.

References:
- [Auth0 Custom Log Streams](https://auth0.com/docs/customize/log-streams/custom-log-streams)

---

### 1.5 Supabase (Database-Level Webhooks)

Supabase implements webhooks as PostgreSQL triggers using the `pg_net` extension.

**Architecture:**
- Webhooks are wrappers around `AFTER INSERT/UPDATE/DELETE` triggers
- The trigger calls `supabase_functions.http_request()` with URL, method, headers (JSON), body, and timeout
- Async execution via pg_net (up to 200 requests/second)
- Response logs stored in `net._http_response` for 6 hours

**Payload format (automatic):**
```json
{
  "type": "INSERT",
  "table": "my_table",
  "schema": "public",
  "record": { "id": 1, "name": "..." },
  "old_record": null
}
```

**Relevance to FLS:** The trigger-based approach maps well to Django signals. The fixed payload format is a limitation we want to avoid. However, the idea of configuring URL, method, headers, and body per webhook endpoint is directly relevant.

References:
- [Supabase Database Webhooks](https://supabase.com/docs/guides/database/webhooks)
- [pg_net Extension](https://supabase.com/docs/guides/database/extensions/pg_net)

---

### 1.6 NetBox (Jinja2 Template-Based Webhooks in Django)

NetBox is a Django application that implements outbound webhooks with Jinja2-based payload templating. This is the most directly relevant reference implementation for FLS.

**Architecture:**
- Webhooks are triggered by Event Rules attached to model changes (create, update, delete, job start/completion)
- Events are queued to Redis (three priority queues: high, default, low) and processed by `rqworker`
- Success requires 2xx response; failed requests can be manually requeued
- Two-model design: `EventRule` determines *when* to fire; `Webhook` determines *how* to deliver

**Webhook model fields** (source: `extras/models/models.py:146-284`):
- `name` - unique identifier
- `payload_url` - destination endpoint (supports Jinja2)
- `http_method` - GET, POST, PATCH, PUT, DELETE
- `http_content_type` - MIME type (default: `application/json`)
- `additional_headers` - custom headers as `Name: Value` lines (supports Jinja2)
- `body_template` - Jinja2 template for the request body
- `secret` - HMAC signing key
- `ssl_verification` - boolean for TLS cert validation (default: True)
- `ca_file_path` - path to custom CA certificate bundle

**EventRule model** (source: `extras/models/models.py:43-144`):
- `object_types` - which models trigger the rule
- `event_types` - creation, update, deletion, job start/completion
- `conditions` - JSON-based conditional logic evaluated against event data
- `action_type` - webhook, script, or notification
- `action_object` - the referenced Webhook or Script instance

**Jinja2 templating for three fields:**
- `payload_url` - the destination endpoint (can be dynamic)
- `additional_headers` - custom HTTP headers
- `body_template` - the request body

**Available template context variables:**
- `event` - trigger type (created, updated, deleted)
- `model` - model class in `app_label.model_name` format
- `timestamp` - ISO 8601 formatted
- `username` - user associated with the change
- `request_id` - unique correlation ID
- `data` - full object representation (matching REST API serialization)
- `snapshots` - pre-change and post-change object states (dict with `prechange` and `postchange` keys)

**Execution flow** (source: `extras/webhooks.py:27-101`, `extras/signals.py:96-134`):
1. Django signal fires on model save/delete
2. System evaluates enabled EventRule instances against conditions
3. Matching webhooks are enqueued to Redis task queue
4. Worker renders Jinja2 templates for headers and body with context variables
5. HMAC signature computed if secret is configured
6. HTTP request sent to payload_url
7. Success/failure captured in logs

**Example body_template for Slack:**
```jinja2
{
  "text": "New {{ model }} created: {{ data.name }} by {{ username }}"
}
```

**Default behavior:** If no body_template is defined, the full context is dumped as JSON.

**HMAC Signing:**
- Uses HMAC-**SHA512** (not SHA256) of the request body
- Hex-encoded digest placed in `X-Hook-Signature` header
- Consumers verify by recomputing the digest with the shared secret

**Security:** Only trusted users should be able to create/modify webhooks, since templates can contain arbitrary Jinja2 code. NetBox includes a built-in `webhook_receiver` management command for local testing.

**Relevance to FLS:** This is the closest match to our needs. A Django app using Jinja2 templates for URL, headers, and body, with context variables populated from model/event data. The two-model design (EventRule + Webhook) cleanly separates "when to fire" from "how to deliver," which is a pattern FLS should adopt. The conditional logic on EventRules (JSON-based conditions) is also worth considering.

References:
- [NetBox Webhooks Documentation](https://netboxlabs.com/docs/netbox/integrations/webhooks/)
- [NetBox Webhook Body Template Discussion](https://github.com/netbox-community/netbox/discussions/9130)
- [NetBox Event Rules (GitHub)](https://github.com/netbox-community/netbox/issues/4237)
- [NetBox Webhooks and Event Rules - DeepWiki](https://deepwiki.com/netbox-community/netbox/8.2-webhooks-and-event-rules)
- [NetBox Source: extras/webhooks.py](https://github.com/netbox-community/netbox/blob/main/netbox/extras/webhooks.py)
- [NetBox Source: extras/models/models.py](https://github.com/netbox-community/netbox/blob/main/netbox/extras/models/models.py)

---

### 1.7 Zapier / n8n / Make (Workflow Automation)

These platforms sit between event producers and consumers, providing visual workflow builders.

**Zapier:**
- Receives webhooks via "Catch Hook" trigger URLs
- Transforms data through visual field mapping or code steps (Python/JavaScript)
- Sends to destination APIs via pre-built "Action" integrations
- Handles auth via OAuth or API key per connected app
- Webhooks are a premium feature (gated behind paid plans)
- Code steps are sandboxed: no package imports beyond a small whitelist, 30-second execution limit, 256MB memory cap

**n8n (open source):**
- Webhook node receives events and parses HTTP payload into structured JSON
- Workflow nodes chain transformations as a directed graph
- Supports JavaScript/Python code nodes for custom transformation with npm package access
- Full execution logs with node-by-node inspection for debugging
- Self-hostable, no restrictions on code step capabilities

**Make (Make.com):**
- Visual workflow builder with automatic payload structure detection
- Webhook module catches payloads and determines data structure automatically
- Best suited for complex visual data transformations
- Less developer-friendly than n8n for custom code transformations

**Key insight for FLS design:** If you need to transform a webhook payload in a non-trivial way, both Zapier and Make force workarounds, while n8n lets you just write the function. FLS should aim for n8n-level directness: the admin writes a Jinja2 template and sees exactly what the output will be.

**Relevance to FLS:** These are external middleware solutions. They solve the same problem but add operational complexity and cost. Our goal is to build a lightweight equivalent directly into FLS so admins do not need a separate Zapier/n8n account. However, we should still support forwarding to Zapier/n8n webhooks as a destination.

References:
- [Zapier Webhooks Guide](https://help.zapier.com/hc/en-us/articles/8496083355661-How-to-get-started-with-Webhooks-by-Zapier)
- [n8n Webhook Node Docs](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [n8n Webhook Integrations](https://n8n.io/integrations/webhook/)

---

### 1.8 Brevo Event Tracking API (The Target Use Case)

Brevo is a specific integration target for FLS. When a student registers or completes a course, FLS needs to notify Brevo so it can trigger marketing automations. Brevo does not receive standard webhooks; it exposes specific REST APIs that expect particular payload formats.

**Two API versions exist:**

#### v2 Track Event API (Automation/Marketing)
- **Endpoint:** `POST https://in-automate.brevo.com/api/v2/trackEvent`
- **Auth header:** `ma-key: YOUR_MA_KEY` (marketing automation key)
- **Content-Type:** `application/json`

**Request body fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `email` | string | Yes | Identifies the contact |
| `event` | string | Yes | Event name to track |
| `properties` | object | No | Custom fields that populate the contact database |
| `eventdata` | object | No | Data about the event (e.g. `eventdata.data.added_product`) |

**Constraint:** Do not use reserved keys (`email` or `event`) in the `properties` object.

**Response:** 204 (success, no content) or 400 (bad request).

#### v3 Events API (Newer, recommended)
- **Endpoint:** `POST https://api.brevo.com/v3/events`
- **Auth header:** `api-key: YOUR_API_KEY`
- **Content-Type:** `application/json`

**Request body fields:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `event_name` | string | Yes | Event identifier (255 chars max, alphanumeric and `-_` only) |
| `identifiers` | object | Yes | At least one contact identifier required |
| `identifiers.email_id` | string | No | Contact email |
| `identifiers.ext_id` | string | No | External ID |
| `identifiers.contact_id` | integer | No | Brevo internal ID (takes priority) |
| `event_date` | string | No | ISO timestamp (defaults to creation time) |
| `event_properties` | object | No | Custom event data (50KB limit, keys 255 chars max) |
| `contact_properties` | object | No | Updates contact attributes (e.g. `"FIRSTNAME": "Jane"`) |

**Response:** 204 (success, no content) or 400/401 (error with `code` and `message`).

**Example FLS-to-Brevo translation (v3):**

Given an FLS `user.registered` event with payload:
```json
{"user": {"email": "jane@example.com", "first_name": "Jane", "last_name": "Doe"}}
```

The Jinja2 body_template would be:
```jinja2
{
  "event_name": "user_registered",
  "identifiers": {"email_id": "{{ data.user.email }}"},
  "contact_properties": {
    "FIRSTNAME": "{{ data.user.first_name }}",
    "LASTNAME": "{{ data.user.last_name }}"
  },
  "event_properties": {
    "source": "freedom_ls",
    "registration_date": "{{ timestamp }}"
  }
}
```

And the headers template:
```
api-key: {{ secrets.brevo_api_key }}
Content-Type: application/json
```

**Relevance to FLS:** This is the primary motivating use case. The Brevo API demonstrates exactly why we need per-endpoint payload transformation: Brevo does not accept a generic webhook payload. The translation layer must restructure FLS event data into Brevo's specific schema, with Brevo-specific auth headers.

References:
- [Brevo Track Custom Events (v2)](https://developers.brevo.com/docs/track-custom-events-rest)
- [Brevo Create Event API (v3)](https://developers.brevo.com/reference/create-event)
- [Brevo Events Overview](https://developers.brevo.com/docs/events)
- [Brevo Event Endpoints](https://developers.brevo.com/docs/event-endpoints)

---

## 2. Key Architectural Patterns

### 2.1 Payload Transformation Approaches

| Approach | Used By | Pros | Cons |
|---|---|---|---|
| **JavaScript handler function** | Svix, Hookdeck | Powerful, flexible, familiar | Needs sandboxing, security risk |
| **Jinja2 templates** | NetBox, Grafana OnCall | Python-native, admin-friendly, no sandbox needed | Less powerful than code, harder to debug complex logic |
| **Visual field mapping** | Zapier | No-code friendly | Requires a UI builder, limited flexibility |
| **Fixed payload (no transformation)** | Stripe, Auth0, Supabase | Simplest to implement | Requires consumer-side middleware |

**Recommendation for FLS:** Jinja2 templates are the best fit. They are Python-native (Django already uses Jinja2-compatible templating), admin-configurable, and do not require sandboxing a code execution runtime. NetBox proves this approach works well in production Django applications.

### 2.2 Authentication / Headers Patterns

Platforms handle outbound auth headers in several ways:

1. **Static headers per endpoint** - Admin configures key-value pairs stored in the database (NetBox, Supabase)
2. **Template-rendered headers** - Headers can include dynamic values from the event context via Jinja2 (NetBox)
3. **Secret references in headers** - Headers reference named secrets that are resolved at send time (Hookdeck via `process.env`)
4. **OAuth flow** - Platform handles token exchange on behalf of the user (Svix connectors, Zapier)

**Recommendation for FLS:** Static headers with secret references. Store secrets encrypted in the database or in environment variables. Allow headers to reference secrets via template syntax, e.g. `{"api-key": "{{ secrets.brevo_api_key }}"}`. Avoid implementing OAuth flows unless specifically needed.

### 2.3 Secrets Management

| Pattern | Used By | Notes |
|---|---|---|
| Environment variables | Hookdeck | Simple, but not per-endpoint |
| Secret fields on endpoint model | Svix, Stripe | Per-endpoint, stored encrypted |
| Django settings / env vars | NetBox | Global, not per-endpoint |

**Recommendation for FLS:** A `WebhookSecret` model (name + encrypted value) that can be referenced in templates. Secrets should never appear in logs, admin list views, or API responses. Use Django's `signing` module or `Fernet` encryption for storage.

### 2.4 Event Naming Convention

The dominant convention across platforms is `resource.action`:
- Stripe: `payment_intent.succeeded`, `customer.subscription.deleted`
- Svix: User-defined event types following the same pattern
- Django-rest-hooks: `book.added`, `book.changed`, `book.removed`

**Recommendation for FLS:** Adopt `resource.action` naming, e.g. `user.registered`, `course.completed`, `cohort.student_added`.

### 2.5 Delivery and Retry

Every platform implements the same core pattern:
1. Events are queued (Redis, PostgreSQL, or a message broker)
2. Workers deliver asynchronously
3. Expect 2xx within a timeout (typically 5-30 seconds)
4. Retry with exponential backoff on failure
5. Disable endpoint after sustained failures

**Recommendation for FLS:** Use Celery (already available via django-webhook) or Django-Q2 for async delivery. Implement exponential backoff retries. Log all attempts for audit purposes.

### 2.6 Payload Signing (HMAC)

HMAC-SHA256 is the industry standard, used by ~65% of webhook implementations:
- Provider signs the request body with a shared secret
- Signature is sent in a header (e.g. `X-Webhook-Signature`)
- Consumer verifies by recomputing the signature
- Include a timestamp to prevent replay attacks
- Use constant-time comparison to prevent timing attacks

**Recommendation for FLS:** Sign all outbound payloads with HMAC-SHA256. Include timestamp. Use the format `t=<timestamp>,v1=<signature>` (Stripe convention). This is for standard webhook consumers; for API translation (e.g. Brevo), signing may not be relevant since the external API has its own auth.

---

## 3. Django-Specific Solutions

### 3.1 django-webhook

A plug-and-play app for sending outgoing webhooks on model changes.

- Leverages Django signals + Celery for async delivery
- Automatic webhook sending on model create/update/delete
- HMAC signature authentication
- Retries with exponential backoff
- Admin integration and audit logging
- Payload includes `topic`, `object`, `object_type`, `webhook_uuid`

**Limitation:** No payload transformation. The payload format is fixed. This solves standard webhook delivery but not the translation problem.

References:
- [django-webhook docs](https://django-webhook.readthedocs.io/)
- [django-webhook on Django Packages](https://djangopackages.org/packages/p/django-webhook/)

### 3.2 django-rest-hooks (by Zapier)

REST Hooks framework using Django signals.

- Hooks into `post_save` and `post_delete` signals automatically
- Event config via `HOOK_EVENTS` setting mapping event names to `App.Model.Action`
- Users subscribe to events via a REST API (self-service)
- Custom serialization via `serialize_hook()` method on models
- Supports custom events via `hook_event` signal and raw events via `raw_hook_event`
- Delivery via threading (default) or Celery (`HOOK_DELIVERER` setting)

```python
HOOK_EVENTS = {
    'user.registered': 'accounts.User.created',
    'user.updated': 'accounts.User.updated+',  # + = all users
    'user.logged_in': None,  # custom event, no model
}
```

**Limitation:** Serialization is per-model, not per-endpoint. All subscribers to `user.registered` get the same payload. No per-destination transformation.

References:
- [django-rest-hooks GitHub](https://github.com/zapier/django-rest-hooks)

### 3.3 drf-hooks

Fork/evolution of django-rest-hooks for Django REST Framework.

- Similar signal-based architecture
- `HOOK_EVENTS` and `HOOK_SERIALIZERS` in settings
- Supports built-in CRUD and custom actions

References:
- [drf-hooks GitHub](https://github.com/am-flow/drf-hooks)

### 3.4 Svix Python SDK

Svix offers a Python SDK for sending webhooks through their hosted service.

- Offloads delivery, retries, and signing to Svix infrastructure
- Django integration guide available
- Requires external service dependency

References:
- [Svix Python/Django Guide](https://www.svix.com/guides/sending/send-webhooks-with-python-django/)

### 3.5 Assessment: What Exists vs. What We Need

| Feature | django-webhook | django-rest-hooks | drf-hooks | What FLS needs |
|---|---|---|---|---|
| Signal-based triggering | Yes | Yes | Yes | Yes |
| Async delivery (Celery) | Yes | Optional | Optional | Yes |
| Retry with backoff | Yes | No | No | Yes |
| HMAC signing | Yes | No | No | Yes |
| Per-endpoint payload transformation | No | No | No | **Yes** |
| Per-endpoint custom headers | No | No | No | **Yes** |
| Per-endpoint secrets | No | No | No | **Yes** |
| Jinja2 body templates | No | No | No | **Yes** |
| Admin-configurable | Partial | No | No | **Yes** |

**Conclusion:** No existing Django package solves the full problem. The closest approach would be combining django-webhook's delivery infrastructure (Celery, retries, HMAC) with NetBox's Jinja2 template pattern for per-endpoint payload transformation.

---

## 4. Summary of Recommendations for FLS

1. **Event naming:** Use `resource.action` convention (e.g. `user.registered`)
2. **Transformation approach:** Jinja2 templates for URL, headers, and body per webhook endpoint
3. **Secrets:** Dedicated model with encrypted storage, referenceable in templates
4. **Delivery:** Celery task queue with exponential backoff retries
5. **Signing:** HMAC-SHA256 with timestamp for standard webhook consumers
6. **Admin interface:** Full Django admin support for configuring endpoints, templates, and secrets
7. **Default behavior:** If no body template is defined, send the full event payload as JSON (NetBox pattern)
8. **Audit trail:** Log all delivery attempts with status codes and response bodies

The NetBox webhook implementation is the strongest reference architecture for our use case: a Django application that needs admin-configurable outbound event forwarding with per-endpoint payload transformation via Jinja2 templates.
