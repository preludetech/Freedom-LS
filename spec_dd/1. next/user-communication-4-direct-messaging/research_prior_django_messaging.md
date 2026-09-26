# Research: Django In-App Messaging Systems

## 1. Existing Django Packages

### django-postman

- **PyPI**: https://pypi.org/project/django-postman/
- **Docs**: https://django-postman.readthedocs.io/
- **Latest version**: 4.5.1 (November 2024)
- **Maintenance**: Classified as "Sustainable" by Snyk. Maintained by Jeff Triplett, sponsored by REVSYS. Low activity (870 weekly downloads, fewer than 10 contributors).
- **Django support**: Django 3.2+ through 5.x
- **Features**:
  - User-to-user private messaging with inbox/outbox/trash
  - Conversation threading
  - Moderation system (pending/accepted/rejected states)
  - Anonymous user support (visitors can message registered users)
  - Exchange filters (blacklists, blocking)
  - Autocomplete recipient fields (django-ajax-selects)
  - Notification integration (pinax-notifications)
  - Unread message filtering, message limits via query params
  - Multiple recipients support
- **Pros**:
  - Feature-rich and mature
  - Good documentation
  - Active (released in 2024)
  - Moderation system useful for educational contexts
- **Cons**:
  - Heavy for simple use cases -- moderation, anonymous messaging, and filters add complexity we may not need
  - Small community, limited contributors
  - Uses its own views and templates extensively -- hard to integrate into an existing HTMX-based UI
  - Tightly coupled to its own URL structure and template patterns
  - Original source hosted on Bitbucket, GitHub mirrors are forks

**Verdict**: Too feature-heavy and opinionated for our needs. The view/template layer would conflict with our HTMX approach.

---

### django-messages

- **PyPI**: https://pypi.org/project/django-messages/
- **Docs**: https://django-messages.readthedocs.io/en/latest/
- **GitHub**: https://github.com/arneb/django-messages
- **Latest version**: 0.6.0
- **Maintenance**: Appears unmaintained. No recent releases. Last significant activity years ago.
- **Features**:
  - Simple inbox/outbox/trash per user
  - No external dependencies beyond Django
  - Basic compose/reply/delete operations
- **Pros**:
  - Simple and minimal
  - No external dependencies
- **Cons**:
  - No conversation threading -- messages are flat
  - No read receipt tracking beyond basic "read" flag
  - Appears abandoned / unmaintained
  - Does not support modern Django versions out of the box

**Verdict**: Too old and unmaintained. No threading support.

---

### pinax-messages

- **PyPI**: https://pypi.org/project/pinax-messages/
- **GitHub**: https://github.com/pinax/pinax-messages
- **Latest version**: 3.0.0
- **Last commit**: June 2021
- **Maintenance**: Effectively unmaintained. Last release supports Django 2.2/3.0 and Python 3.6-3.8 only.
- **Features**:
  - Thread-based messaging (Thread + Message models)
  - Inbox view, thread detail view, compose view
  - Template tags for unread counts (`unread` filter, `unread_thread_count`)
  - `Message.new_message()` class method for programmatic message creation
  - `message_sent` signal for custom integrations
  - Context processor for inbox data
- **Pros**:
  - Clean Thread/Message architecture
  - Signal-based integration pattern worth studying
  - `new_message()` API is a good design pattern
- **Cons**:
  - Unmaintained since 2021
  - Does not support Django 4.x or 5.x
  - No read receipt timestamps (only boolean read tracking)
  - Small feature set

**Verdict**: Unmaintained, but the Thread/Message model pattern and signal design are worth studying as reference.

---

### django-conversation

- **PyPI**: https://pypi.org/project/django-conversation/
- **Snyk**: https://snyk.io/advisor/python/django-conversation
- **Features**:
  - Threaded conversations between users
  - Conversations related to a user (all messages between user1 and user2 in one thread)
  - Can attach a content object to a conversation (GenericForeignKey)
  - Email notifications on new messages
- **Pros**:
  - Threaded model
  - Content-object attachment is interesting (could link conversations to courses/cohorts)
- **Cons**:
  - Maintenance status unclear
  - Limited documentation
  - Small user base

**Verdict**: Interesting content-object linking, but too risky to depend on.

---

### django-threaded-messages

- **PyPI**: https://pypi.org/project/django-threaded-messages/
- **Features**:
  - Facebook-style threading (each message is a thread with participants)
  - Inbox with read/unread filtering
  - Outbox
  - Batch operations (mark read/unread/delete)
  - Fulltext search via Haystack
- **Pros**:
  - Feature-rich threading
  - Batch operations
- **Cons**:
  - Haystack dependency for search
  - Maintenance status unclear
  - Likely outdated

**Verdict**: Overkill and likely outdated.

---

### Overall Recommendation

**Build a custom messaging app.** None of the existing packages are both well-maintained and aligned with our needs (HTMX views, optional/toggleable app, simple educator-student messaging). The data model patterns from these packages (especially pinax-messages and the Reintech article) provide solid reference designs. Building custom gives us full control over the HTMX integration and the ability to keep it simple.

---

## 2. Data Model Patterns

### Pattern A: Simple Message Model (Flat)

```python
class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sent_messages", on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="received_messages", on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
```

- **Pros**: Dead simple. One table. Easy queries.
- **Cons**: No concept of a conversation. Finding "all messages between user A and user B" requires filtering on both directions. No natural grouping for thread display.
- **When to use**: If messaging is strictly 1-to-1 and the UI just shows a flat message history between two users.

**This is likely sufficient for FLS.** The idea doc describes simple educator-student messaging, one-to-one, with a scrollable history. A conversation/thread model adds complexity without clear benefit when conversations are always between exactly two known users.

### Pattern B: Conversation/Thread Model

```python
class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

- **Pros**: Clean grouping. Easy to list "all conversations for user X". Natural fit for group messaging later. `updated_at` on conversation enables sorting inbox by most recent activity.
- **Cons**: Extra table and join. Need logic to find or create the right conversation when composing. ManyToManyField adds complexity for what is currently always a 2-person conversation.
- **When to use**: When you need an inbox view listing conversations, or when group messaging is a possibility.

**Reference**: This is the pattern used by pinax-messages (Thread + Message) and recommended by the [Reintech article](https://reintech.io/blog/building-a-messaging-system-in-django).

### Pattern C: Hybrid (Flat messages with computed threads)

Use the simple message model (Pattern A) but add a `thread_id` or query messages between two users as a virtual thread:

```python
class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sent_messages", on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="received_messages", on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sender", "recipient", "-created_at"]),
            models.Index(fields=["recipient", "is_read"]),
        ]
```

Thread queries become:
```python
Message.objects.filter(
    Q(sender=user_a, recipient=user_b) | Q(sender=user_b, recipient=user_a)
).order_by("created_at")
```

- **Pros**: Simple model, no extra tables, thread is a query pattern rather than a model.
- **Cons**: Slightly more complex queries. Listing "all conversations for a user" requires a subquery or annotation to get the latest message per conversation partner.
- **When to use**: When the conversation is always 1-to-1 and you want simplicity.

---

### Read Tracking Approaches

#### Approach 1: Per-message boolean flag

```python
is_read = models.BooleanField(default=False)
read_at = models.DateTimeField(null=True, blank=True)
```

- **Pros**: Simple. One field on the message. No extra table. Easy to query unread count: `Message.objects.filter(recipient=user, is_read=False).count()`.
- **Cons**: Only works for 1-to-1 messaging. In group messaging, different recipients read at different times.
- **Best for**: Our use case (educator-student 1-to-1).

#### Approach 2: Separate read-receipt model

```python
class MessageStatus(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="statuses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("message", "user")
```

- **Pros**: Supports group messaging (each participant has their own read state). Can track delivery status separately. More extensible.
- **Cons**: Extra table, extra join on every query. Creates N rows per message (one per participant). Overkill for 1-to-1.
- **Best for**: Group messaging or when rich delivery/read status tracking is needed.

**Reference**: [Reintech: Building a Messaging System in Django](https://reintech.io/blog/building-a-messaging-system-in-django), [Pusher: Build read receipts using Django](https://pusher.com/tutorials/read-receipts-django/)

**Recommendation for FLS**: Use the per-message boolean approach. It is sufficient for 1-to-1 educator-student messaging and avoids unnecessary complexity. If group messaging is needed later, a migration to a separate model is straightforward.

---

### "Load Older Messages on Scroll Up" (Cursor-Based Pagination)

The idea doc specifically calls for loading only the latest messages and loading older ones on scroll-up. This is a classic cursor-based pagination pattern.

#### Why cursor-based (not offset-based)?

- **Offset pagination** (`?page=2`) breaks when new messages arrive -- items shift between pages.
- **Cursor pagination** uses a pointer (typically a timestamp or ID) to say "give me N messages before this point." Stable regardless of new inserts.

**Reference**: [Django REST Framework: CursorPagination](https://www.django-rest-framework.org/api-guide/pagination/), [django-cursor-pagination](https://github.com/photocrowd/django-cursor-pagination), [django-infinite-scroll-pagination](https://github.com/nitely/django-infinite-scroll-pagination)

#### Implementation pattern for HTMX

Since FLS uses HTMX (not DRF), we implement cursor pagination manually:

```python
# View
def message_history(request, other_user_id):
    before_id = request.GET.get("before")  # cursor: message ID
    messages = Message.objects.filter(
        Q(sender=request.user, recipient_id=other_user_id) |
        Q(sender_id=other_user_id, recipient=request.user)
    ).select_related("sender")

    if before_id:
        messages = messages.filter(id__lt=before_id)

    messages = messages.order_by("-created_at")[:PAGE_SIZE]
    has_older = messages.count() == PAGE_SIZE

    return render(request, "messaging/_message_list.html", {
        "messages": reversed(list(messages)),  # oldest first for display
        "has_older": has_older,
        "oldest_id": messages[-1].id if messages else None,
    })
```

```html
<!-- HTMX trigger for loading older messages -->
{% if has_older %}
<div hx-get="{% url 'messaging:history' other_user.id %}?before={{ oldest_id }}"
     hx-trigger="intersect once"
     hx-swap="afterbegin"
     hx-target="#message-list">
    Loading older messages...
</div>
{% endif %}
```

Key points:
- Use `id__lt` as the cursor (IDs are monotonically increasing)
- `hx-trigger="intersect once"` fires when the sentinel div scrolls into view
- `hx-swap="afterbegin"` prepends older messages above existing ones
- Using ID rather than timestamp avoids issues with identical timestamps

---

## 3. Best Practices for a Pluggable/Optional Django Messaging App

### Making It Toggleable via Settings

The idea doc states: "The messaging app can be turned on and off using configuration."

#### Pattern: Conditional INSTALLED_APPS

```python
# settings.py
ENABLE_MESSAGING = env.bool("ENABLE_MESSAGING", default=False)

INSTALLED_APPS = [
    # ... core apps ...
]

if ENABLE_MESSAGING:
    INSTALLED_APPS.append("freedom_ls.messaging")
```

This is the simplest and most Django-idiomatic approach. When the app is not in `INSTALLED_APPS`:
- Its models/tables are not created by `migrate`
- Its URLs are not registered
- Its template tags are not available

**Reference**: [Django Forum: INSTALLED_APPS can they be optional?](https://forum.djangoproject.com/t/installed-apps-can-they-be-optional/34900), [Django Applications docs](https://docs.djangoproject.com/en/6.0/ref/applications/)

#### Conditional URL inclusion

```python
# config/urls.py
from django.conf import settings

urlpatterns = [...]

if "freedom_ls.messaging" in settings.INSTALLED_APPS:
    urlpatterns += [
        path("messages/", include("freedom_ls.messaging.urls")),
    ]
```

#### Conditional template rendering

For UI elements like "new message" badges that appear outside the messaging app:

```html
{% if "freedom_ls.messaging" in installed_apps %}
    {% include "messaging/_unread_badge.html" %}
{% endif %}
```

Or use a custom template tag that gracefully returns nothing when messaging is disabled. A context processor can inject `messaging_enabled` into all templates:

```python
# freedom_ls/base/context_processors.py
from django.apps import apps

def messaging_context(request):
    return {
        "messaging_enabled": apps.is_installed("freedom_ls.messaging"),
    }
```

---

### Integrating with Existing User Models Without Tight Coupling

#### Use `settings.AUTH_USER_MODEL` in ForeignKey declarations

```python
from django.conf import settings

class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
```

This is the standard Django pattern. It resolves at migration time and works with any custom user model.

**Reference**: [Django: Customizing authentication](https://docs.djangoproject.com/en/6.0/topics/auth/customizing/)

#### Use `get_user_model()` in runtime code

```python
from django.contrib.auth import get_user_model

def get_unread_count(user):
    User = get_user_model()
    # ...
```

**Important**: Never call `get_user_model()` at module level in `models.py` (causes circular imports). Use it inside functions/methods, or use `settings.AUTH_USER_MODEL` for string references.

---

### Signal-Based vs Direct Integration

#### Signal-based approach

The messaging app emits signals that other apps can listen to:

```python
# freedom_ls/messaging/signals.py
from django.dispatch import Signal

message_sent = Signal()  # provides: sender, message, recipient
message_read = Signal()  # provides: sender, message, reader
```

```python
# freedom_ls/messaging/models.py
from .signals import message_sent

class Message(models.Model):
    def save(self, **kwargs):
        is_new = self._state.adding
        super().save(**kwargs)
        if is_new:
            message_sent.send(sender=self.__class__, message=self, recipient=self.recipient)
```

Other apps connect without importing messaging models:

```python
# freedom_ls/student_interface/apps.py
class StudentInterfaceConfig(AppConfig):
    def ready(self):
        from django.apps import apps
        if apps.is_installed("freedom_ls.messaging"):
            from freedom_ls.messaging.signals import message_sent
            message_sent.connect(handle_new_message)
```

- **Pros**: Fully decoupled. Other apps never import messaging models. Messaging app has no knowledge of other apps.
- **Cons**: Indirection makes the code harder to trace. Signal handlers can silently fail.

#### Direct integration approach

Other apps import messaging utilities directly, guarded by availability checks:

```python
def send_welcome_message(student, educator):
    try:
        from freedom_ls.messaging.services import send_message
    except ImportError:
        return  # messaging not installed
    send_message(sender=educator, recipient=student, body="Welcome!")
```

- **Pros**: Explicit. Easy to follow. No hidden side effects.
- **Cons**: Creates an import-time dependency (though guarded). Caller must know messaging API.

#### Recommendation

Use **both** strategically:
- **Signals** for the messaging app to notify the outside world (e.g., "a message was sent" so notification badges can update).
- **Direct imports with guards** when other apps need to actively send messages (e.g., an educator action triggers a message). This is more explicit and easier to debug.

**Reference**: [pinax-messages signal pattern](https://github.com/pinax/pinax-messages), [Caktus Group: Making your Django app more pluggable](https://www.caktusgroup.com/blog/2013/06/12/making-your-django-app-more-pluggable/)

---

## Summary of Recommendations for FLS

| Decision | Recommendation | Rationale |
|---|---|---|
| Build vs Buy | Build custom | No well-maintained package fits our HTMX stack and toggleable requirement |
| Data model | Flat messages (Pattern C: hybrid) | 1-to-1 educator-student only; conversation is a query, not a model |
| Read tracking | Per-message boolean + timestamp | Sufficient for 1-to-1; simple queries |
| Pagination | Cursor-based (by ID) with HTMX `intersect` trigger | Stable under concurrent writes; matches "scroll up for older" UX |
| Toggleability | Conditional `INSTALLED_APPS` + context processor | Standard Django pattern; clean on/off |
| User model coupling | `settings.AUTH_USER_MODEL` in models, `get_user_model()` in runtime | Standard Django decoupling |
| Integration pattern | Signals for outbound notifications, guarded imports for inbound actions | Balance of decoupling and explicitness |
