"""The helper that reads a UUID pk from a query string or a URL."""

from __future__ import annotations

from uuid import UUID

from django.http import Http404

__all__ = [
    "uuid_or_404",
]


def uuid_or_404(raw: str | None) -> UUID:
    """A pk from a query string or a URL; a 404 when it is not a UUID."""
    try:
        return UUID(raw or "")
    except ValueError:
        raise Http404("not a uuid") from None
