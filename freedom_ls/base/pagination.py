"""Query-string paging shared by every pager on the learner dashboard."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from django.core.paginator import Page, Paginator
from django.http import QueryDict

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet
    from django.http import HttpRequest


def clamped_page(
    request: HttpRequest,
    param_name: str,
    object_list: Sequence[object] | QuerySet[Model],
    per_page: int,
) -> Page:
    """The page of ``object_list`` that ``request.GET[param_name]`` names, clamped to a valid page.

    ``get_page`` rather than ``page``: a home page must not 500 on a stale
    bookmark or a hand-edited query string, so a junk page number clamps.

    ``get_page`` on its own clamps a non-integer to page one but clamps
    anything below page one to the *last* page (Django's ``EmptyPage``
    covers both "too high" and "too low", and ``get_page`` maps every
    ``EmptyPage`` to ``num_pages``). A below-range page number is treated
    here the same as a non-integer: it clamps to page one.
    """
    paginator = Paginator(object_list, per_page)
    raw_value = request.GET.get(param_name)
    page_value: str | None = raw_value
    if raw_value is not None:
        try:
            if int(raw_value) < 1:
                page_value = "1"
        except ValueError:
            pass
    return paginator.get_page(page_value)


def page_href(request: HttpRequest | None, param_name: str, page_number: int) -> str:
    """The current URL showing ``page_number`` of one pager.

    Copies the incoming query string and touches only this pager's key, so
    every other pager's page survives the link and an unrecognised parameter
    passes through with no allowlist to maintain. Page one drops the key.

    With no request there is no URL to copy, so the link is the query string
    alone, which the browser resolves against the page it is on.
    """
    query = request.GET.copy() if request is not None else QueryDict(mutable=True)
    path = request.path if request is not None else ""
    if page_number <= 1:
        query.pop(param_name, None)
    else:
        query[param_name] = str(page_number)
    encoded = query.urlencode()
    return f"{path}?{encoded}" if encoded else path


def position_text(page: Page) -> str:
    """The range a page shows, as every dashboard pager words it: "1 to 3 of 7"."""
    return f"{page.start_index()} to {page.end_index()} of {page.paginator.count}"
