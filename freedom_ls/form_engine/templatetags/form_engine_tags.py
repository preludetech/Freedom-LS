"""Template tags for the form_engine app."""

from __future__ import annotations

from django import template

from freedom_ls.form_engine.uploads import (
    ACCEPT_ATTRIBUTE,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_LABEL,
)

register = template.Library()


@register.simple_tag
def upload_limits() -> dict[str, object]:
    """The upload caps, so no template hard-codes a number the validator owns."""
    return {
        "max_bytes": MAX_UPLOAD_BYTES,
        "accept": ACCEPT_ATTRIBUTE,
        "max_label": MAX_UPLOAD_LABEL,
    }
