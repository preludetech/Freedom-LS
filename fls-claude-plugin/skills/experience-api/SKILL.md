---
name: experience-api
description: Work with the xAPI event tracking system. Use when adding a new event type to a domain app, emitting a new event from a view/service, querying events, or debugging a failed track() call. Triggers on tracking, xAPI, events, verbs, "track()", emitting events.
allowed-tools: Read, Grep, Glob
---

# xAPI Event Tracking (`experience_api`)

This skill helps work with FLS's lightweight xAPI-style event log.

## When to Use This Skill

Use this skill when:
- **Emitting an event from a view or service** — pick the right domain-app wrapper (`track_topic_viewed`, `track_form_completed`, ...)
- **Adding a new `(verb, object_type)` pair** — schemas and wrappers live in the owning domain app's `xapi_events.py`, not in `experience_api`
- **Querying events** — typed-column filters, JSONB containment
- **Debugging** — `TrackingSchemaError`, strict-vs-permissive, immutability errors
- **Running erasure** — the `erase_actor` management command

## Headline Rules

- **Events are immutable.** Never call `Event.objects.create()` directly. Never modify an existing row. The only permitted mutation is the audited `erase_actor` flow, which runs through a separate DB role.
- **Every FK on `Event` is nullable.** Pointers may dangle — snapshots are the source of truth for the audit record.
- **Every schema field that snapshots something is required at write time.** The paired `_id` field is the nullable pointer; the `_slug` / `_title` / `_name` snapshot is required.
- **Verbs come from `experience_api.verbs`.** Don't invent new IRIs — reuse ADL verbs.
- **Schemas live in the owning domain app.** `student_interface/xapi_events.py` and `student_progress/xapi_events.py` own their event types; `experience_api` contains only generic infrastructure.
- **Inside `experience_api`, only import from `accounts` and `site_aware_models`** (plus `experience_api` itself). This keeps the app portable — the import-boundary test enforces it.

## Where Things Live

| What | Where |
|---|---|
| Generic `track()` helper | `freedom_ls/experience_api/tracking.py` |
| Verb constants | `freedom_ls/experience_api/verbs.py` |
| Schema registry | `freedom_ls/experience_api/registry.py` |
| `BaseEventSchema` and size caps | `freedom_ls/experience_api/schema_base.py` |
| `Event` and `ActorErasure` models | `freedom_ls/experience_api/models.py` |
| `erase_actor` / `maintain_event_partitions` | `freedom_ls/experience_api/management/commands/` |
| Domain-app schemas + wrappers | `freedom_ls/<app>/xapi_events.py` |
| Shared snapshot helpers (content) | `freedom_ls/content_engine/xapi_snapshots.py` |
| Shared snapshot helpers (registrations / cohorts) | `freedom_ls/student_management/xapi_snapshots.py` |

## Emitting an Existing Event

Call the domain-app wrapper, not `track()` directly:

```python
from freedom_ls.student_interface.xapi_events import track_topic_viewed

track_topic_viewed(request.user, topic, request=request,
                   referrer=request.META.get("HTTP_REFERER"))
```

## Adding a New Event Type — in Brief

1. Decide which app **owns** the event (where is it emitted from?).
2. Add the verb constant to `experience_api.verbs` if it doesn't exist.
3. Define the Pydantic schema in the owning app's `xapi_events.py`.
4. Register it: `register_event_type(VERB, "ObjectType", MySchema)` at module top.
5. Add snapshot helpers where the models live (`content_engine/xapi_snapshots.py` etc.).
6. Add a `track_<object>_<verb>` wrapper.
7. Wire the wrapper into the originating view/service. Test.

For the full recipe see `${CLAUDE_PLUGIN_ROOT}/resources/experience_api.md`.
