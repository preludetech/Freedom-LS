from __future__ import annotations

from django.http import Http404


class OrganisationScopeDenied(Http404):
    """The instance exists but is outside request.organisation.

    A distinct type from a bare Http404 so a switch handler can tell "wrong
    organisation" apart from every other reason path resolution 404s (an
    unknown segment, a missing tab, a deleted object). panel_framework never
    catches this specially — it is an Http404, so anything that does not
    look for it treats it exactly like one.
    """
