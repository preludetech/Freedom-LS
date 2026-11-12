# Technical Patterns for Pluggable In-App Feedback Systems in Django

Research into architecture patterns, existing packages, and implementation strategies for building a configurable, hookable feedback system in Django 6.x with HTMX, TailwindCSS, and Alpine.js.

## 1. Signal/Hook Patterns for Configurable Feedback Triggers

### Option A: Django Custom Signals

Django's built-in signal dispatcher implements the Observer pattern. Custom signals can be defined for feedback-worthy events and any installed app can connect receivers.

```python
# feedback/signals.py
import django.dispatch

feedback_trigger = django.dispatch.Signal()  # sends: trigger_name, user, context

# In the LMS core (e.g. after course completion):
feedback_trigger.send(
    sender=CourseProgress,
    trigger_name="course_completed",
    user=request.user,
    context={"course_id": course.id},
    request=request,
)
```

**Pros:**
- Built into Django, no extra dependencies
- Decoupled -- the feedback app does not need to know about the sender
- Well-understood pattern in the Django ecosystem

**Cons:**
- Signals are synchronous by default; a slow feedback handler blocks the request
- Debugging signal chains is harder than explicit function calls
- No built-in priority/ordering for multiple receivers
- David Seddon and Lincoln Loop both caution against overusing signals for core business logic -- they work best for cross-cutting concerns like notifications, which is exactly what feedback is

**References:**
- [Django Signals documentation](https://docs.djangoproject.com/en/5.1/topics/signals/)
- [When to Use Django Signals (David Seddon)](https://seddonym.me/2018/05/04/django-signals/)
- [Django Anti-Patterns: Signals (Lincoln Loop)](https://lincolnloop.com/blog/django-anti-patterns-signals/)

### Option B: Hook Registry Pattern

A registry-based approach where trigger points explicitly call into a hook registry. This is what [django-hooks](https://github.com/nitely/django-hooks) implements.

```python
# feedback/registry.py
class FeedbackHookRegistry:
    _hooks: dict[str, list[Callable]] = {}

    @classmethod
    def register(cls, trigger_name: str, handler: Callable) -> None:
        cls._hooks.setdefault(trigger_name, []).append(handler)

    @classmethod
    def fire(cls, trigger_name: str, **kwargs) -> list:
        results = []
        for handler in cls._hooks.get(trigger_name, []):
            results.append(handler(**kwargs))
        return results
```

**Pros:**
- Explicit and easy to debug (you can inspect the registry)
- Supports ordering and priority
- Can return values (signals return values too, but it is less idiomatic)

**Cons:**
- Another pattern to learn; not standard Django
- Registration timing matters (must happen in `AppConfig.ready()`)

**References:**
- [django-hooks (nitely)](https://github.com/nitely/django-hooks) -- provides TemplateHook, FormHook, and SignalHook
- [DJP: A plugin system for Django (Simon Willison)](https://simonwillison.net/2024/Sep/25/djp-a-plugin-system-for-django/)
- [django-plugin-system](https://dev.to/alireza_tabatabaeian_a4f6/building-a-pluggable-architecture-in-django-introducing-django-plugin-system-2da2)

### Option C: Middleware + Context Processor

A middleware checks each response for feedback trigger conditions (e.g. session flags set by views) and injects feedback modal HTML or a trigger flag into the response context.

**Pros:**
- Centralized; one place controls all feedback injection
- Does not require views to know about feedback at all

**Cons:**
- Coarse-grained; hard to pass rich context about what happened
- Middleware runs on every request, so conditions must be cheap to evaluate
- Harder for downstream apps to customize

### Recommendation for FLS

**Use Django custom signals as the primary trigger mechanism.** Feedback is a textbook cross-cutting concern -- exactly where signals shine. The feedback app registers a receiver that checks whether a feedback form is configured for the given trigger, and if so, sets a session flag. The HTMX response then picks up this flag.

For downstream apps that install FLS, they simply connect to `feedback_trigger` or fire it from their own views. No FLS code changes required.

---

## 2. Configurable Form Systems

### Option A: Model-Based Dynamic Forms

Store form definitions in the database. Each form has a set of related field definitions (field type, label, required, choices, ordering).

```
FeedbackForm
  - name, description, trigger_name, is_active

FeedbackFormField
  - form (FK), field_type (choices: text, textarea, rating, select, checkbox),
    label, help_text, required, choices_json, order
```

**Pros:**
- Admin-configurable without code changes or deployments
- Can be managed per-site in a multi-tenant setup (using site-aware models)
- Easy to add/remove/reorder fields
- Natural fit for Django admin

**Cons:**
- Rendering dynamic forms requires a form factory function
- Validation logic is limited to what you build into the field types
- More complex than static forms

### Option B: JSON Schema Forms

Store the entire form definition as a JSON schema in a single JSONField. Use a library like [django-jsonform](https://github.com/bhch/django-jsonform) to render the schema in the admin.

```python
class FeedbackForm(models.Model):
    name = models.CharField(max_length=200)
    trigger_name = models.CharField(max_length=100, unique=True)
    schema = models.JSONField()  # JSON Schema defining the form
```

**Pros:**
- Maximum flexibility in a single field
- JSON Schema is a well-known standard
- Can be exported/imported easily

**Cons:**
- Harder for non-technical admins to edit (even with django-jsonform)
- Validation and rendering require a JSON Schema -> Django Form translation layer
- Harder to query individual field values

**References:**
- [django-jsonform](https://github.com/bhch/django-jsonform)
- [django-jsonschema-form](https://github.com/catallog/django-jsonschema-form)
- [django-form-builder](https://github.com/UniversitaDellaCalabria/django-form-builder)

### Option C: Hardcoded Forms with Registry

Define feedback forms as regular Django Form classes, registered via a hook system. Downstream apps create their own Form subclasses and register them.

```python
# In a downstream app
from feedback.registry import FeedbackHookRegistry

class PostCourseForm(forms.Form):
    rating = forms.IntegerField(min_value=1, max_value=5)
    comment = forms.CharField(widget=forms.Textarea, required=False)

FeedbackHookRegistry.register("course_completed", PostCourseForm)
```

**Pros:**
- Full power of Django forms (custom validation, widgets, clean methods)
- Type-safe; IDE support
- No dynamic form generation complexity

**Cons:**
- Requires a code deployment to change forms
- Not admin-configurable

### Recommendation for FLS

**Use the model-based dynamic forms approach (Option A).** This fits FLS's multi-site architecture -- each site can have its own feedback forms configured via the admin. The field type choices should be kept small and focused (text, textarea, rating 1-5, single select, multi select). A form factory function generates Django Form instances from the database definitions at render time.

For downstream apps that need maximum customization, also support Option C as an escape hatch -- allow registering a custom Django Form class that overrides the dynamic form for a given trigger.

---

## 3. Trigger Point Architecture

A "trigger point" is a place in the code where a feedback prompt might be shown. The system needs to:
1. Define standard trigger points in FLS
2. Allow downstream apps to define their own trigger points
3. Let admins configure which trigger points have active feedback forms

### Pattern: Named Trigger Points with Signal

```python
# In a view or service layer:
from feedback.signals import feedback_trigger

def complete_course(request, course_id):
    # ... mark course complete ...
    feedback_trigger.send(
        sender=self.__class__,
        trigger_name="course_completed",
        user=request.user,
        context={"course": course},
        request=request,
    )
```

The feedback app's receiver:
```python
@receiver(feedback_trigger)
def handle_feedback_trigger(sender, trigger_name, user, context, request, **kwargs):
    form = FeedbackForm.objects.filter(
        trigger_name=trigger_name, is_active=True, site=get_current_site(request)
    ).first()
    if form and not already_responded(user, form, context):
        request.session["pending_feedback"] = {
            "form_id": form.id,
            "context": serialize_context(context),
        }
```

### Standard FLS Trigger Points

Based on the idea.md, initial trigger points would include:
- `course_completed` -- after a student completes a course
- `activity_completed` -- after completing an activity
- `topic_completed` -- after completing a topic

Downstream apps add their own by simply firing `feedback_trigger.send(...)` from their views.

### Conditions and Throttling

The `FeedbackForm` model should support conditions:
- `cooldown_days` -- don't show the same form to the same user within N days
- `max_responses` -- limit total responses per user for this form
- `show_probability` -- only show to a percentage of users (A/B testing)

**References:**
- [django-action-triggers](https://django-action-triggers.readthedocs.io/en/latest/) -- trigger/action pattern for Django
- [edx-django-utils App Plugins](https://docs.openedx.org/projects/edx-django-utils/en/latest/plugins/readme.html) -- how Open edX handles plugin discovery
- [django-waffle](https://waffle.readthedocs.io/en/stable/) -- feature flag conditions pattern (useful for show_probability)

---

## 4. Storage Patterns for Feedback Responses

### Option A: JSONField on a Single Response Model

```python
class FeedbackResponse(SiteAwareModel):
    form = models.ForeignKey(FeedbackForm, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    response_data = models.JSONField()  # {"rating": 4, "comment": "Great course"}
    trigger_context = models.JSONField()  # {"course_id": 42}
    created_at = models.DateTimeField(auto_now_add=True)
```

**Pros:**
- Simple schema; one table for all feedback
- Works with any form structure without migrations
- PostgreSQL supports indexing and querying inside JSONField
- Easy to export

**Cons:**
- Cannot enforce constraints at the DB level
- Aggregation queries (e.g. average rating) require JSON path expressions
- No referential integrity for field values

### Option B: EAV (Entity-Attribute-Value)

Separate tables for responses and individual field values.

```
FeedbackResponse -> has many FeedbackFieldValue
FeedbackFieldValue: response (FK), field (FK to FeedbackFormField), value_text, value_int, value_bool
```

**Pros:**
- Strongly typed values; can use proper DB types per field type
- Easier aggregation (AVG on value_int for rating fields)
- Referential integrity to field definitions

**Cons:**
- Many rows per response; more JOINs
- Complex queries
- Performance degrades with scale

**References:**
- [django-eav2](https://github.com/jazzband/django-eav2)
- [django-jeaves (EAV using JSONField)](https://github.com/zostera/django-jeaves)
- [Flexible Data Models with JSONField and Pydantic](https://dev.to/dannyell77/how-to-build-flexible-data-models-in-django-with-jsonfield-and-pydantic-13hi)

### Recommendation for FLS

**Use JSONField (Option A).** Feedback responses are write-heavy, read-occasionally data. The simplicity of a single JSONField outweighs the querying limitations. For reporting needs (e.g. average rating), use PostgreSQL's JSON operators or materialize aggregations in application code.

Validate the JSON structure against the form definition at write time in the Django form's `clean()` method, so invalid data never reaches the database.

---

## 5. HTMX Integration Patterns

### Pattern A: Session Flag + Lazy Load on Page Navigation

1. Signal handler sets `request.session["pending_feedback"]`
2. A base template includes a feedback container that lazy-loads on every page:

```html
<!-- base.html -->
<div id="feedback-modal-container"
     hx-get="{% url 'feedback:check_pending' %}"
     hx-trigger="load"
     hx-swap="innerHTML">
</div>
```

3. The `check_pending` view returns empty HTML if no feedback is pending, or returns the modal HTML if there is pending feedback.

**Pros:**
- Decoupled from individual views; works on any page
- Does not slow down the main page load (lazy loaded)
- The feedback app only needs one URL added

**Cons:**
- Extra HTTP request on every page load (but returns empty 204 when no feedback)
- Slight delay before modal appears

### Pattern B: HX-Trigger Response Header

After a feedback-triggering action (e.g. marking a course complete via HTMX), the view sets an HX-Trigger response header that causes the client to fetch the feedback form.

```python
# In the course completion view
response = render(request, "course_complete.html")
if pending_feedback:
    response["HX-Trigger"] = json.dumps({
        "showFeedback": {"form_id": form.id}
    })
return response
```

```html
<!-- In base.html -->
<div id="feedback-modal-container"
     hx-get="{% url 'feedback:get_form' %}"
     hx-trigger="showFeedback from:body"
     hx-vals="js:event.detail"
     hx-swap="innerHTML">
</div>
```

**Pros:**
- No extra request on pages without feedback
- Immediate trigger after the action
- Works naturally with HTMX's event system

**Cons:**
- Requires the triggering view to know about feedback (or use a middleware that adds the header)
- Only works for HTMX responses, not full page loads

### Pattern C: Out-of-Band Swap

Include the feedback modal as an out-of-band swap in the response to a feedback-triggering HTMX request.

```html
<!-- Returned alongside the main response content -->
<div id="feedback-modal-container" hx-swap-oob="innerHTML">
    <dialog class="modal" x-data x-init="$el.showModal()">
        <!-- feedback form here -->
    </dialog>
</div>
```

**Pros:**
- Single response; no extra requests
- Immediate display

**Cons:**
- Tightly couples the triggering view to feedback rendering
- Only works for HTMX requests
- Harder to make pluggable

### Pattern D: Alpine.js + Custom Events

Use Alpine.js to manage modal state, triggered by HTMX events.

```html
<div x-data="{ showFeedback: false, formId: null }"
     @show-feedback.window="showFeedback = true; formId = $event.detail.form_id">
    <template x-if="showFeedback">
        <div hx-get="/feedback/form/"
             hx-vals="js:{form_id: formId}"
             hx-trigger="load"
             hx-target="#feedback-form-content">
            <dialog x-init="$el.showModal()" @close="showFeedback = false">
                <div id="feedback-form-content"></div>
            </dialog>
        </div>
    </template>
</div>
```

**Pros:**
- Clean separation: Alpine handles UI state, HTMX handles server communication
- Uses the native `<dialog>` element for accessibility (focus trapping, escape key)
- Fully decoupled from triggering views

**Cons:**
- Requires both Alpine.js and HTMX coordination

### Recommendation for FLS

**Use a combination of Pattern A (session flag + lazy load) for full page loads and Pattern B (HX-Trigger header) for HTMX responses.** This covers both scenarios. Use Alpine.js with the native `<dialog>` element for the modal itself (Pattern D's UI approach).

A middleware can handle injecting the HX-Trigger header automatically when `request.session["pending_feedback"]` is set, keeping individual views completely unaware of the feedback system.

**References:**
- [HTMX Custom Modal Dialogs example](https://htmx.org/examples/modal-custom/)
- [Django+HTMX modal form (Benoit Blanchon)](https://blog.benoitblanchon.fr/django-htmx-modal-form/)
- [Show Django forms inside a modal using HTMX (Josh Karamuth)](https://joshkaramuth.com/blog/django-htmx-modal-forms/)
- [Build a Reusable Component with Django Cotton and AlpineJS](https://joshkaramuth.com/blog/django-cotton-alpine-component/)
- [django-htmx-patterns: Modal dialogs](https://github.com/spookylukey/django-htmx-patterns/blob/master/modals.rst)
- [Out-of-band swaps with HTMX (JetBrains)](https://www.jetbrains.com/guide/dotnet/tutorials/htmx-aspnetcore/out-of-band-swaps/)
- [HTMX lazy loading discussion](https://github.com/bigskysoftware/htmx/discussions/2736)

---

## 6. Existing Django Packages

### Survey/Feedback Packages

| Package | Stars | Status | Notes |
|---------|-------|--------|-------|
| [django-form-surveys](https://github.com/irfanpule/django-form-surveys) | ~150 | Active | Admin-configurable surveys, anonymous submissions, email notifications. Most feature-complete for surveys. |
| [django-survey-and-report](https://github.com/Pierre-Sassoulas/django-survey) | ~400 | Active | CSV/PDF export, multi-language. Fork of django-survey with Python 3 support. Good for reporting. |
| [django-crowdsourcing](https://pythonhosted.org/django-crowdsourcing/) | ~100 | Inactive | Developed for NY Public Radio. Highly configurable but no longer maintained. |

**What they do well:**
- Admin interfaces for creating surveys
- Multiple question types (text, rating, multiple choice)
- Response collection and basic reporting

**What they do poorly:**
- None support trigger-based/contextual display (they are all standalone survey pages)
- No HTMX integration
- No multi-site awareness
- No hook/signal system for triggering from other apps
- Not designed as pluggable components for embedding in other apps

### Plugin/Hook Packages

| Package | Notes |
|---------|-------|
| [django-hooks](https://github.com/nitely/django-hooks) | TemplateHook, FormHook, SignalHook. Good concepts but low maintenance. |
| [DJP](https://simonwillison.net/2024/Sep/25/djp-a-plugin-system-for-django/) | Simon Willison's plugin system built on Pluggy. Modern, well-designed. For app-level plugins. |
| [django-plugin-system](https://dev.to/alireza_tabatabaeian_a4f6/building-a-pluggable-architecture-in-django-introducing-django-plugin-system-2da2) | Inspired by Drupal's plugin system. Runtime discovery, admin control. |

### Form Builder Packages

| Package | Notes |
|---------|-------|
| [django-jsonform](https://github.com/bhch/django-jsonform) | JSON editing widget for admin. Would be useful if using JSON Schema forms. |
| [django-form-builder](https://github.com/UniversitaDellaCalabria/django-form-builder) | Dynamic forms from dictionaries/JSON. Could be adapted for feedback forms. |

### Assessment

None of the existing packages provide what FLS needs. The survey packages are standalone page-based tools, not embeddable trigger-based feedback systems. **Building a custom feedback app is the right approach**, but we can learn from their form definition and response storage patterns.

**References:**
- [Django Packages: Survey/Questionnaire grid](https://djangopackages.org/grids/g/survey-questionnaire/)

---

## Summary of Recommendations

| Concern | Recommended Approach |
|---------|---------------------|
| **Trigger mechanism** | Django custom signals (`feedback_trigger`) |
| **Form definition** | Model-based dynamic forms (FeedbackForm + FeedbackFormField) with optional code-defined form override |
| **Trigger points** | Named string identifiers fired via signal; standard ones defined in FLS, extensible by downstream apps |
| **Response storage** | Single `FeedbackResponse` model with JSONField for response data |
| **HTMX integration** | Session flag + lazy load for full pages; HX-Trigger header via middleware for HTMX responses |
| **Modal UI** | Alpine.js + native `<dialog>` element, loaded via HTMX |
| **Multi-site** | All models extend SiteAwareModel; forms configured per site |

### Proposed Model Structure

```
FeedbackForm (SiteAwareModel)
    - name: CharField
    - trigger_name: CharField (e.g. "course_completed")
    - is_active: BooleanField
    - cooldown_days: IntegerField (optional)
    - max_responses_per_user: IntegerField (optional)
    - thank_you_message: TextField

FeedbackFormField
    - form: ForeignKey(FeedbackForm)
    - field_type: CharField (choices: text, textarea, rating, select, checkbox)
    - label: CharField
    - help_text: TextField (optional)
    - required: BooleanField
    - choices_json: JSONField (optional, for select/checkbox)
    - order: IntegerField

FeedbackResponse (SiteAwareModel)
    - form: ForeignKey(FeedbackForm)
    - user: ForeignKey(User, null=True)  # null for anonymous
    - response_data: JSONField
    - trigger_context: JSONField  # e.g. {"course_id": 42}
    - created_at: DateTimeField
```
