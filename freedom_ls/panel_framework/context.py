"""The per-request state a bound panel or action needs to render or submit."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Model
from django.http import HttpRequest


@dataclass(frozen=True, kw_only=True)
class PanelContext:
    """Everything a bound panel or action needs at render time.

    `base_url` is the URL of this panel's own path segment. `name` is this
    panel's key in its parent's `children` dict, and is the empty string for
    a root panel. A container builds each child's context with
    `dataclasses.replace(ctx, base_url=..., name=...)` rather than mutating
    the parent's context, and a new field can be added here with a default
    without breaking any existing subclass.
    """

    request: HttpRequest
    instance: Model | None
    base_url: str
    name: str
