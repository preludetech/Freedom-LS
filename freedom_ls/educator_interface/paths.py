"""URL building shared by the educator interface's views and quick views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse

if TYPE_CHECKING:
    from freedom_ls.organisations.models import Organisation


def interface_path(organisation: Organisation, path_string: str) -> str:
    """The URL of `path_string` inside the organisation's interface."""
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
    )
