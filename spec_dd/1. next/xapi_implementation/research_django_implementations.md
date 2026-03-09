# Research: Django/Python xAPI and Event Tracking Implementations

## 1. Existing Python/Django xAPI Libraries

### TinCanPython (Rustici Software)
- **Status**: Effectively abandoned. Last meaningful update 2021, stuck on v0.0.5.
- Provides Python classes for xAPI statements and an LRS client.
- **Verdict**: Not worth using. Unmaintained, no modern Python testing.
- https://github.com/RusticiSoftware/TinCanPython

### xapi-python
- **Status**: Announced March 2024 on xapi.com. Relatively new, unclear maintenance.
- https://pypi.org/project/xapi-python/
- **Verdict**: Too new and unproven to depend on.

### Ralph (France Universite Numerique / openfun)
- **Status**: Actively maintained. Used in production with Open edX Aspects.
- Full LRS server + CLI + library with Pydantic v2 xAPI statement models.
- **Verdict**: Overkill as a dependency (full LRS), but its Pydantic-based xAPI models are excellent reference material for designing our own lightweight models.
- https://github.com/openfun/ralph

### Recommendation
Build custom. The xAPI statement structure (actor + verb + object + result + timestamp) is simple enough that no library dependency is justified. Use Ralph's models as design reference only.

## 2. Open edX Event Tracking Architecture

Open edX (Django-based) uses three layers -- instructive but over-engineered for FLS:

**Layer 1 -- `event-tracking`** (https://github.com/openedx/event-tracking): Processor/backend pipeline. Events pass through processors in series, then fan out to backends (MongoDB, Segment, logger). A `TrackMiddleware` enriches events with HTTP context automatically.

**Layer 2 -- `openedx-events`** (https://docs.openedx.org/projects/openedx-events/en/latest/concepts/openedx-events.html): Custom `OpenEdxPublicSignal` extending Django signals. Adds metadata (version, timestamp) on `send_event()`. Uses `send_robust()` in production so receivers cannot crash callers. Typed event data via attrs classes.

**Layer 3 -- `event-routing-backends`** (https://github.com/openedx/event-routing-backends): Listens to tracking events, transforms to xAPI or Caliper format, routes to external LRS endpoints via Celery tasks. Transformer classes map internal events to xAPI statements.

**Key takeaway**: The core pattern is sound -- emit structured events internally, transform to xAPI format separately. But three packages + Celery + event bus is far more than FLS needs.

## 3. Django Patterns for Event Tracking

| Pattern | Best for | Avoid when |
|---------|----------|------------|
| **Explicit helper calls** | Semantic events (topic completed, form submitted). Clear, greppable, testable. | N/A -- this is the primary pattern |
| **Django signals** | Avoiding circular deps between apps | Both sender and receiver are in your project and could use a direct call |
| **Middleware** | Injecting request context (user, session) into events | Capturing semantic business events (too coarse-grained) |
| **Decorators** | Simple view-level events (page viewed) | Events needing data computed during the view |

**Recommendation for FLS**: Explicit helper calls as primary pattern. The Django community increasingly advises against signals for app-internal communication (see https://lincolnloop.com/blog/django-anti-patterns-signals/). Middleware is useful only for context injection, not event capture. Our spec says "lightweight" -- signals add indirection we don't need.

## 4. Helper Function API Design

**Good design principles:**

1. **One function per event type** -- not a generic `track()` with string verbs. `track.topic_viewed(user, topic)` is greppable and type-safe.
2. **Accept model instances** -- the helper extracts IDs/names internally. Callers pass `topic`, not `topic.id`.
3. **Minimal required args** -- auto-capture timestamp, site, and session internally.
4. **Verb constants** -- prevent typos. `from xapi.verbs import COMPLETED, VIEWED`.
5. **Return the created event** -- useful for testing: `event = track.topic_viewed(user, topic)`.
6. **Never raise exceptions** -- tracking failures must not break the user's action. Wrap in try/except internally.
7. **Synchronous by default** -- write to Postgres directly. Add async later if needed.

**Example ergonomic API:**
```python
from freedom_ls.xapi import track
track.topic_viewed(user=request.user, topic=topic)
track.form_submitted(user=request.user, form=form, score=85, max_score=100)
track.course_enrolled(user=request.user, course=course)
```

**Anti-patterns to avoid:**
- Generic `track_event(verb="completed", object_type="topic", object_id=42)` -- forces callers to know internal structure
- Raw dict API -- `emit({"actor": {"mbox": ...}, ...})` -- no validation, no discoverability
- Too many required params -- callers should not pass timestamp, IP, user-agent, etc.

## 5. Lessons Learned / Common Mistakes

1. **Tracking too much too early.** Start with 5-10 high-value events (enrolled, topic viewed, form submitted, activity completed, course completed). Add more based on actual analytical needs.

2. **Inconsistent verb vocabulary.** "opened" vs "accessed" vs "viewed" for the same action. Define verb constants early and enforce through typed helpers.

3. **Storing results in wrong xAPI fields.** Scores belong in `result.score`, not `context.extensions`. Get basic structure right from day one.

4. **Not capturing context at event time.** Record cohort, course version, and site with each event. Don't rely on JOINs -- users change cohorts, courses get updated.

5. **Overwriting historical data.** Events must be immutable (append-only). Each attempt is a separate event. Current status is derived from event history.

6. **Data volume surprises.** xAPI generates far more data than SCORM-style tracking. Index on (user, verb, object, timestamp). Consider date-based partitioning. Avoid high-frequency events (video heartbeats) until there's a proven need.

7. **Coupling to full xAPI compliance too early.** Use xAPI concepts (actor/verb/object) as naming conventions, but store in simple queryable format. Add full xAPI serialization as an export feature later. (This aligns with Moodle's approach: log internally first, convert to xAPI for export.)

8. **Ignoring multi-site concerns.** Every event must be scoped to a site. FLS already has site-aware models -- the xAPI app must follow the same pattern.

## References

- [TinCanPython](https://github.com/RusticiSoftware/TinCanPython)
- [xapi-python on PyPI](https://pypi.org/project/xapi-python/)
- [Ralph LRS](https://github.com/openfun/ralph) | [Docs](https://openfun.github.io/ralph/latest/)
- [Open edX event-tracking](https://github.com/openedx/event-tracking)
- [Open edX Events](https://docs.openedx.org/projects/openedx-events/en/latest/concepts/openedx-events.html)
- [Open edX event-routing-backends](https://github.com/openedx/event-routing-backends)
- [Open edX Event Bus Architecture (OEP-52)](https://docs.openedx.org/projects/openedx-proposals/en/latest/architectural-decisions/oep-0052-arch-event-bus-architecture.html)
- [Django Anti-Patterns: Signals](https://lincolnloop.com/blog/django-anti-patterns-signals/)
- [Events and Handlers Instead of Signals](https://botched-deployments.com/posts/2024/events-and-handlers-instead-of-signals-in-django)
- [10 Best Practices for xAPI Statements](https://www.learningguild.com/articles/10-best-practices-for-xapi-statements)
- [xAPI Overview](https://xapi.com/overview/)
- [Moodle logstore_xapi Plugin](https://github.com/xAPI-vle/moodle-logstore_xapi)
