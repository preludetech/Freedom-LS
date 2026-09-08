"""The dashboard's paginated sections: their identity, page state and links.

A section is the unit the dashboard renders and pages independently. Its slug
names its page parameter (``page_<slug>``) and every id the template and the
htmx swap need, so a category slug can never collide with a built-in section's
ids however it is authored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.paginator import Paginator

if TYPE_CHECKING:
    from django.core.paginator import Page
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_recommendations.models import RecommendedCourse

SECTION_PAGE_SIZE = 3


def _page_param_name(slug: str) -> str:
    return f"page_{slug}"


@dataclass(frozen=True)
class DashboardSection:
    """One rendered dashboard section, already sorted, paged and annotated.

    ``page_obj`` holds whatever the paginator was given, which for Recommended
    courses is ``RecommendedCourse`` rows rather than courses. Templates read
    ``courses`` for cards and ``page_obj`` only for pagination state.
    """

    slug: str
    heading: str
    wrapper_id: str
    page_obj: Page
    courses: list[Course]
    description: str = ""
    browse_all_url: str = ""

    @property
    def page_param_name(self) -> str:
        return _page_param_name(self.slug)

    @property
    def heading_id(self) -> str:
        return f"section-heading-{self.slug}"

    @property
    def swap_id(self) -> str:
        return f"section-page-{self.slug}"

    @property
    def position_text(self) -> str:
        if self.page_obj.paginator.count == 0:
            return ""
        return (
            f"{self.page_obj.start_index()} to {self.page_obj.end_index()} "
            f"of {self.page_obj.paginator.count}"
        )

    @property
    def nav_label(self) -> str:
        return f"{self.heading} pages"


def page_for(
    request: HttpRequest,
    slug: str,
    object_list: QuerySet[Course] | list[Course] | list[RecommendedCourse],
) -> Page:
    """This section's page of ``object_list``, clamped to a valid page.

    ``get_page`` rather than ``page``: a home page must not 500 on a stale
    bookmark or a hand-edited query string, so a junk page number clamps.
    """
    return Paginator(object_list, SECTION_PAGE_SIZE).get_page(
        request.GET.get(_page_param_name(slug))
    )


def section_page_href(request: HttpRequest, param_name: str, page_number: int) -> str:
    """The dashboard URL showing ``page_number`` of one section.

    Copies the incoming query string and touches only this section's key, so
    every other section's page survives the link and an unrecognised parameter
    passes through with no allowlist to maintain. Page one drops the key.
    """
    query = request.GET.copy()
    if page_number <= 1:
        query.pop(param_name, None)
    else:
        query[param_name] = str(page_number)
    encoded = query.urlencode()
    return f"{request.path}?{encoded}" if encoded else request.path
