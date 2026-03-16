# Research: Django Integration for Outbound Webhooks

## 1. Current Project State

### Task System
The project (Django 5.x) does **not** currently use any background task framework. No Celery, Huey, django-q, or django-tasks is installed. The `pyproject.toml` lists `celery.*` in mypy overrides (ignore_missing_imports) but Celery is not an actual dependency.

The `idea.md` states: "Webhooks should make use of the tasks api." This refers to a task system that needs to be introduced.

### Recommended Task Framework: `django-tasks`

`django-tasks` is a backport of Django 6.0's built-in Tasks framework (DEP 0014) that works with Django 4.2+/5.x.

- **PyPI**: https://pypi.org/project/django-tasks/
- **GitHub**: https://github.com/RealOrangeOne/django-tasks
- **Django 6.0 docs** (upstream API): https://docs.djangoproject.com/en/6.0/topics/tasks/

Why this over Celery:
- Lighter weight -- no Redis/RabbitMQ broker dependency required
- Follows the Django standard that will be built-in from Django 6.0
- The project can migrate to `django.tasks` when upgrading to Django 6.0 with minimal changes
- Provides `ImmediateBackend` (dev) and `DummyBackend` (testing) out of the box
- Database-backed worker available via `django-tasks[django_tasks.backends.database]`

### Existing Patterns
- **No Django signals** are used anywhere in the codebase currently.
- **No event/hook system** exists yet.
- The project uses `SiteAwareModel` for multi-site support -- webhooks will need to be site-aware using the same pattern.
- The `student_progress` app has explicit function calls like `update_course_progress_on_completion()` -- the codebase favors explicit calls over implicit signal-based patterns.

---

## 2. Triggering Webhooks: Signals vs Explicit Calls vs Service Layer

### Option A: Django Signals (`post_save`, custom signals)

**Pros:**
- Decoupled -- webhook app doesn't need to know about every caller
- Easy to add new event sources without touching existing code

**Cons:**
- Implicit coupling makes debugging harder (hard to trace what triggers what)
- `post_save` fires before `transaction.commit` -- the data may not be visible to the webhook consumer yet
- Signals can fire unexpectedly (e.g., during data migrations, fixture loading, bulk operations)
- Django's own docs caution against signals when sender and receiver are in the same project

**Verdict:** Not recommended as the primary trigger mechanism.

Ref: https://seddonym.me/2018/05/04/django-signals/

### Option B: Explicit Function Calls (recommended)

A utility function like `fire_webhook_event("user.registered", payload, site=site)` called explicitly at the point where the event occurs.

**Pros:**
- Easy to trace, debug, and test
- Consistent with how the existing codebase works (see `update_course_progress_on_completion`)
- Full control over when it fires (can be placed after `transaction.on_commit`)
- Clear about what data is included in the payload

**Cons:**
- Every call site needs to import and call the function
- Adding a new event requires touching the code where the event happens

**Verdict:** Best fit for this project. Matches existing patterns.

### Option C: Service Layer / Domain Events

A service layer where all business logic lives, and events are emitted as a side effect of service methods.

**Pros:**
- Clean separation of concerns
- Events are a natural byproduct of business operations

**Cons:**
- Requires refactoring the entire codebase to route through services
- Over-engineered for the current project size

**Verdict:** Good future direction but not practical to adopt now.

---

## 3. Decoupling Delivery from Request/Response

Webhook HTTP delivery MUST NOT happen in the request/response cycle. If the target server is slow or down, it would block the user's request.

### Recommended Pattern

```
View/Business Logic
  --> transaction.on_commit(lambda: enqueue_webhook_task(event, payload))
      --> django-tasks worker picks up task
          --> HTTP POST to webhook URL
              --> Record success/failure in WebhookDeliveryAttempt
```

Key points:

1. **`transaction.on_commit`**: Ensures the webhook is only queued after the database transaction commits. If the transaction rolls back, no webhook fires. This prevents sending webhooks for data that doesn't exist.
   - Ref: https://hakibenita.com/django-reliable-signals

2. **Task queue (`django-tasks`)**: The actual HTTP POST happens in a background worker. This means:
   - The user's request returns immediately
   - Retries are handled by the task system
   - Failed deliveries don't crash the application

3. **Idempotency**: Each webhook delivery should include a unique `event_id` (UUID) so consumers can deduplicate.

---

## 4. Webhook Management Admin Interface

Based on common patterns from production webhook systems (Stripe, GitHub, Zapier's django-rest-hooks), admins typically need:

### Configuration (WebhookEndpoint model)
- **Target URL** -- the HTTPS endpoint to POST to
- **Site** -- which site this webhook belongs to (SiteAwareModel)
- **Events** -- which event types trigger this webhook (e.g., `user.registered`, `progress.completed`)
- **Secret key** -- auto-generated HMAC secret for payload signing (so consumers can verify authenticity)
- **Active/inactive toggle** -- disable without deleting
- **Headers** (optional) -- custom headers to include (e.g., API keys for the target)

### Monitoring (WebhookDeliveryAttempt model)
- **Event type and payload** -- what was sent
- **HTTP status code** -- what the target returned
- **Response body** (truncated) -- for debugging
- **Timestamp** -- when delivery was attempted
- **Success/failure status**
- **Retry count** -- how many times delivery was attempted
- **Next retry at** -- when the next retry is scheduled (if failed)

### Admin UX Features
- List view filtered by endpoint, event type, success/failure
- Manual retry button for failed deliveries
- Test/ping button to send a test payload to an endpoint
- Delivery success rate summary per endpoint

### Retry Strategy
- Exponential backoff: retry at 1min, 5min, 30min, 2hrs, 12hrs
- Max 5 retries, then mark as permanently failed
- Only retry on network errors and 5xx responses (not 4xx -- those indicate a problem on the consumer side)

---

## 5. Proposed Models (high-level)

```
WebhookEndpoint (SiteAwareModel)
    - url: URLField
    - secret: CharField (auto-generated)
    - events: JSONField (list of event type strings)
    - is_active: BooleanField
    - created_at, updated_at

WebhookDeliveryAttempt
    - endpoint: FK(WebhookEndpoint)
    - event_type: CharField
    - event_id: UUIDField
    - payload: JSONField
    - status_code: IntegerField (nullable)
    - response_body: TextField (truncated)
    - success: BooleanField
    - attempt_number: IntegerField
    - created_at: DateTimeField
```

---

## 6. Utility Function API (sketch)

```python
from django.db import transaction

def fire_webhook_event(event_type: str, payload: dict, site: Site) -> None:
    """Queue webhook delivery for all active endpoints subscribed to this event on this site."""
    transaction.on_commit(lambda: _enqueue_webhook_deliveries(event_type, payload, site))
```

This is what app code would call. The function itself:
1. Looks up active `WebhookEndpoint` records for the given site + event_type
2. Creates a `WebhookDeliveryAttempt` record for each
3. Enqueues a `django-tasks` task for each delivery

---

## 7. Key References

- Django Tasks framework (Django 6.0 docs): https://docs.djangoproject.com/en/6.0/topics/tasks/
- django-tasks backport: https://github.com/RealOrangeOne/django-tasks
- When to Use Django Signals (David Seddon): https://seddonym.me/2018/05/04/django-signals/
- Reliable Django Signals / transaction.on_commit: https://hakibenita.com/django-reliable-signals
- django-rest-hooks (Zapier): https://github.com/zapier/django-rest-hooks
- django-webhook (model-change triggered): https://github.com/danihodovic/django-webhook
- Django Packages -- Webhooks grid: https://djangopackages.org/grids/g/webhooks/
- Better Stack guide to Django background tasks: https://betterstack.com/community/guides/scaling-python/django-background-tasks/
