"""Schema registry for ``(verb, object_type)`` pairs.

The registry lives as a module-level dict; domain apps register their
schemas in their ``apps.py.ready()`` by importing their ``xapi_events``
module (which calls :func:`register_event_type` at import time).

Idempotent re-registration of the *same* schema class is allowed — Django's
``ready()`` can fire twice under some test configurations.  Registering a
*different* schema class for an already-registered key raises — that is
always a mistake, never a legitimate reconfiguration.
"""

from __future__ import annotations

from .exceptions import TrackingSchemaError
from .schema_base import BaseEventSchema
from .verbs import Verb

REGISTRY: dict[tuple[Verb, str], type[BaseEventSchema]] = {}


def register_event_type(
    verb: Verb, object_type: str, schema_cls: type[BaseEventSchema]
) -> None:
    """Register ``schema_cls`` as the validator for ``(verb, object_type)``.

    Idempotent for same-class re-registration; raises :class:`RuntimeError`
    for conflicting registrations.
    """
    key = (verb, object_type)
    existing = REGISTRY.get(key)
    if existing is not None and existing is not schema_cls:
        raise RuntimeError(
            f"Event type {(verb.display, object_type)!r} already registered "
            f"with a different schema class: {existing!r} vs {schema_cls!r}."
        )
    REGISTRY[key] = schema_cls


def get_schema(verb: Verb, object_type: str) -> type[BaseEventSchema]:
    """Look up the schema registered for ``(verb, object_type)``.

    Raises :class:`TrackingSchemaError` when the pair has no registration —
    error message names the verb display and object-type string only.
    """
    try:
        return REGISTRY[(verb, object_type)]
    except KeyError:
        raise TrackingSchemaError(
            f"No schema registered for (verb={verb.display!r}, "
            f"object_type={object_type!r})."
        ) from None
