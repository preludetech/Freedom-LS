"""The dashboard's paginated sections: their identity, page state and links.

A section is the unit the dashboard renders and pages independently. Its slug
names its page parameter (``page_<slug>``) and every id the template and the
htmx swap need, so a category slug can never collide with a built-in section's
ids however it is authored.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from freedom_ls.base import pagination

if TYPE_CHECKING:
    from django.core.paginator import Page
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_recommendations.models import RecommendedCourse

SECTION_PAGE_SIZE = 3
SECTION_SWAP_ID_PREFIX = "section-page-"


class BuiltInSection(StrEnum):
    """The slugs of the sections the dashboard always owns.

    Mirrors ``RESERVED_SECTION_SLUGS`` in ``content_engine.schema``, which
    refuses these as category slugs; a test keeps the two sets equal.
    """

    IN_PROGRESS = "in-progress"
    RECOMMENDED = "recommended"
    AVAILABLE = "available"
    COMING_SOON = "coming-soon"
    HISTORY = "history"


def _page_param_name(slug: str) -> str:
    return f"page_{slug}"


def requested_section_slug(request: HttpRequest) -> str | None:
    """The slug of the section an htmx page request names in ``HX-Target``.

    ``None`` for anything else, including a boosted navigation, which must get
    the whole page.
    """
    if request.headers.get("HX-Request") != "true":
        return None
    target = request.headers.get("HX-Target", "")
    if not target.startswith(SECTION_SWAP_ID_PREFIX):
        return None
    return target[len(SECTION_SWAP_ID_PREFIX) :]


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
        return f"{SECTION_SWAP_ID_PREFIX}{self.slug}"

    @property
    def is_empty(self) -> bool:
        return self.page_obj.paginator.count == 0

    @property
    def renders_when_empty(self) -> bool:
        """In progress is the one section with empty-state copy."""
        return self.slug == BuiltInSection.IN_PROGRESS

    @property
    def position_text(self) -> str:
        if self.is_empty:
            return ""
        return pagination.position_text(self.page_obj)

    @property
    def status_text(self) -> str:
        """What the live region announces after this section's page swaps."""
        if self.is_empty:
            return "nothing to show"
        return f"showing {self.position_text}"

    @property
    def nav_label(self) -> str:
        return f"{self.heading} pages"


def page_for(
    request: HttpRequest,
    slug: str,
    object_list: QuerySet[Course] | list[Course] | list[RecommendedCourse],
) -> Page:
    """This section's page of ``object_list``, clamped to a valid page."""
    return pagination.clamped_page(
        request, _page_param_name(slug), object_list, SECTION_PAGE_SIZE
    )
