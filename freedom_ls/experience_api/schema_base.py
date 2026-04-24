"""Base Pydantic schema and shared size-cap constants.

Domain apps subclass :class:`BaseEventSchema` to describe the shape of a
single ``(verb, object_type)`` pair. The shape is three nested models
(``ObjectDefinition`` / ``Result`` / ``ContextExtensions``) — see
``1. spec.md`` §"Conventions for domain-app schemas".

Size caps below are **conventions**; the schema author applies them per
field via ``Field(max_length=...)`` / ``Field(max_items=...)``. The tracker
enforces the ``HARD_CEILING_BYTES`` ceiling before Pydantic runs, regardless
of schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

# Per-field size conventions — a schema author should import these rather
# than hard-code literals.
STRING_EXTENSION_MAX_LENGTH: int = 2048
RESULT_RESPONSE_MAX_LENGTH: int = 20480
SNAPSHOT_STRING_MAX_LENGTH: int = 512
LIST_EXTENSION_MAX_ITEMS: int = 100

# Hard per-string ceiling the tracker enforces before Pydantic runs. This
# is a DoS-resistance ceiling, not a schema convention: any single string
# longer than this raises TrackingSchemaError immediately.
HARD_CEILING_BYTES: int = 65536


class BaseEventSchema(BaseModel):
    """Base for every ``(verb, object_type)`` schema.

    Subclasses declare nested ``ObjectDefinition``, ``Result``, and
    ``ContextExtensions`` models and reference them as fields here.
    ``extra="forbid"`` rejects unknown top-level keys (the tracker catches
    unknown ``context_extensions`` keys via strict-vs-permissive handling).
    """

    model_config = ConfigDict(extra="forbid")

    object_definition: Any
    result: Any = None
    context_extensions: Any
