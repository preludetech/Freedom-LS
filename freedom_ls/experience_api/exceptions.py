"""Exceptions raised by the experience_api app."""

from __future__ import annotations


class EventImmutableError(Exception):
    """Raised when anything attempts to mutate or delete an Event / ActorErasure row.

    Events are append-only audit records. The only permitted mutation path is the
    narrowly-scoped erasure flow, which operates through a separate DB role entirely
    and so never hits these guards.
    """


class TrackingSchemaError(Exception):
    """Raised when a tracking call fails validation.

    This covers: unregistered `(verb, object_type)` pairs; Pydantic validation
    failures in strict mode; the hard per-string size ceiling; and the
    dangling-pointer guard (populated `_id` with empty snapshot).

    Error messages and logged fields carry field **names** only — never
    caller-supplied values. This is enforced by the tracking module's helpers.
    """
