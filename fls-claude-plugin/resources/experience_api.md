# Experience API — Full Reference

Long-form companion to the `experience-api` skill. Covers recipes for adding event types, emitting events, querying them, and the anti-patterns to avoid.

## Architecture Quick Recap

- **`experience_api`** is generic infrastructure. It persists, validates, and queries xAPI-shaped rows. It doesn't know about topics, forms, or cohorts.
- **Domain apps** own their event types. Each owning app defines its Pydantic schemas, snapshot helpers, and `track_*` wrappers in a file called `xapi_events.py` and registers them at `apps.py.ready()` time.
- **`Event`** is the storage model. Every row is immutable at four layers (save-override, delete-override, manager, pre_save signal) plus DB-level `REVOKE UPDATE, DELETE`.
- **`ActorErasure`** is the erasure audit log. Append-only for everyone — even the erasure role.

## Emit-an-Existing-Event Recipe

1. Look up the wrapper for your `(verb, object_type)` in the owning app's `xapi_events.py`.
2. Check the wrapper's required kwargs. Every kwarg maps to a field in the Pydantic schema.
3. Call the wrapper. Pass `request=request` when available so site / session / UA / IP are derived automatically.
4. The tracker validates before persisting. Strict mode (dev/test default) raises `TrackingSchemaError` on any problem. Permissive mode (prod default) logs at error and drops the event — tracking failures must not break the user's primary action.

### Example

```python
from freedom_ls.student_interface.xapi_events import track_form_completed

track_form_completed(
    request.user, form,
    request=request,
    success=passed,
    score_raw=raw, score_max=max_score, score_scaled=raw / max_score,
    duration="PT5M",
    attempt_number=3,
    pass_threshold=0.7,
    answers_changed=2,
    timed_out=False,
)
```

## Add-a-New-Event-Type Recipe (the seven steps)

### 1. Decide the owning app

Where is the event emitted from? That's the owning app. `experience_api` never owns an event type — it's generic infrastructure.

### 2. Verb constant

Is there already a verb in `experience_api.verbs`? Reuse it. Only add a new verb if the ADL vocabulary has one that fits and `verbs.py` doesn't export it yet. Document why if you invent an IRI that isn't ADL.

### 3. Pydantic schema

In the owning app's `xapi_events.py`:

```python
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

from freedom_ls.experience_api.schema_base import (
    BaseEventSchema, SNAPSHOT_STRING_MAX_LENGTH, STRING_EXTENSION_MAX_LENGTH,
)


class _MyObjectDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    my_id: UUID | None = None
    my_slug: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    my_title: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)


class _MyContextExtensions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID | None = None
    course_slug: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    course_title: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)


class MyEventSchema(BaseEventSchema):
    object_definition: _MyObjectDef
    result: None = None
    context_extensions: _MyContextExtensions
```

Conventions you must follow (enforced by review + per-schema tests):

- Every `_id` is nullable (`UUID | None`).
- The paired `_slug` / `_title` / `_name` snapshot is required.
- Snapshot mutable context fully (titles, thresholds, question text, cohort dates).
- Size-cap every string and list with `Field(max_length=...)` / `Field(max_items=...)`.
- Use `ConfigDict(extra="forbid")` on every nested model so unknown keys are caught.

### 4. Register

At the top of `xapi_events.py`:

```python
from freedom_ls.experience_api.registry import register_event_type
from freedom_ls.experience_api.verbs import MY_VERB

register_event_type(MY_VERB, "MyObject", MyEventSchema)
```

Make sure the owning app's `apps.py.ready()` imports `xapi_events` — otherwise registration never runs:

```python
class StudentInterfaceConfig(AppConfig):
    def ready(self) -> None:
        from freedom_ls.student_interface import xapi_events  # noqa: F401
```

### 5. Snapshot helpers

Pure read helpers live next to the models they walk:

- Content-engine walks → `freedom_ls/content_engine/xapi_snapshots.py`
- Registration / cohort walks → `freedom_ls/student_management/xapi_snapshots.py`

They **never** import from `experience_api`. They're plain functions.

### 6. Wrapper

One wrapper per `(verb, object_type)`:

```python
from freedom_ls.experience_api.tracking import track

def track_my_object_my_verb(
    actor, my_object, *, request=None, strict=None, **extras,
) -> Event | None:
    course = walk_my_object_to_course(my_object)
    return track(
        actor=actor,
        verb=MY_VERB,
        object_type="MyObject",
        object_id=my_object.id,
        object_definition=snapshot_my_object(my_object),
        context_extensions={
            "course_id": course.id if course else None,
            "course_slug": course.slug if course else "",
            "course_title": course.title if course else "",
            **extras,
        },
        request=request,
        strict=strict,
    )
```

Wrapper conventions:

- Name: `track_<object>_<verb>`.
- First positional: the actor. Second positional: the target.
- All other arguments keyword-only.
- Return the `Event` so callers can chain (e.g. `PROGRESSED` via `trigger_event_id`).

### 7. Wire + Test

Call the wrapper from the originating view/service. Write three tests minimum:

- **End-to-end**: invoke the call site; assert exactly one row with the expected shape.
- **Required-field-missing**: call with one required field absent; assert `TrackingSchemaError` and no row written.
- **Deletion-survives**: after the event lands, delete the target; assert the snapshot still reads and the FK column is NULL.

## Querying Events

Typed-column filters work through the ORM:

```python
Event.objects.filter(verb="http://adlnet.gov/expapi/verbs/completed",
                     object_type="Form",
                     actor_user_id=user.id).order_by("-timestamp")
```

JSONB containment on the `context` / `result` / `object_definition` columns:

```python
Event.objects.filter(context__extensions__cohort_id=cohort.id)
```

When running queries in a data-migration or an operator tool (no request in the thread-locals), use `Event._base_manager` to bypass the site-scoped manager.

## Anti-Patterns

- **`Event.objects.create(...)`** — bypasses the tracker flag. Raises `EventImmutableError` by design. Always go through a `track_*` wrapper.
- **Adding an `_id` field without a paired snapshot** — the dangling-pointer guard raises at write time and code review rejects it.
- **Using `on_delete=CASCADE` on any FK into `Event`** — violates the immutability promise; all FKs must be `null=True, on_delete=SET_NULL` (except `site`).
- **Mutating an existing event to "correct" it** — express corrections as new events (`(VOIDED, Statement)` pattern).
- **Using email as an IFI** — the xAPI IFI is `"<site_homepage>|<user.id>"`. Email is captured separately and is cleared by erasure.
- **Putting domain-specific logic inside `experience_api`** — if your change needs to import `content_engine`, `student_management`, or any other FLS-specific app, it belongs in a domain app's `xapi_events.py`, not in `experience_api`.
- **Adding a `**kwargs` pass-through to `track()`** — the generic helper stays free of domain argument names; wrappers own the named kwargs.

## Configuration

| Setting | Dev/Test | Prod | Purpose |
|---|---|---|---|
| `EXPERIENCE_API_STRICT_VALIDATION` | `True` | `False` | Validation failure mode |
| `EXPERIENCE_API_CAPTURE_IP` | `True` | `False` | Record `ip_address`? |
| `EXPERIENCE_API_QUEUED_BACKEND_OBSERVABILITY_OK` | `False` | `False` | Operator ack for non-`ImmediateBackend` |
| `EXPERIENCE_API_ERASURE_BLOCKERS` | list of dotted paths | — | Callables `(user_id) -> bool` that veto erasure |
| `TASKS` | `ImmediateBackend` | `ImmediateBackend` | Task backend — see spec before changing |

## Running Erasure

```
uv run manage.py erase_actor --user-id <int> --confirm [--admin-user-id <int>]
```

- `--confirm` is required always. No dry-run mode yet.
- `--admin-user-id` is required when `STRICT=True` (dev/test default) and strongly recommended always — the audit row captures it as `invoking_admin_user_id`.
- Every configured blocker in `EXPERIENCE_API_ERASURE_BLOCKERS` is consulted. The FLS-default blocker refuses erasure while the user still has active `UserCourseRegistration` rows.
- The command connects via `DATABASES["erasure"]` — a login user that is a member of `fls_erasure_role`. In prod, `FLS_ERASURE_DB_USER` / `FLS_ERASURE_DB_PASSWORD` env vars must be set or the command refuses.
