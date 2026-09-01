import pytest
from playwright.sync_api import Page, expect

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)

from ..conftest import reverse_url

# Long enough that it cannot fit a 375px phone's content well, so the row has
# to truncate rather than widen the page.
LONG_TOPIC_TITLE = (
    "Understanding Advanced Assessment Design and Rubric Calibration in Practice"
)


@pytest.mark.parametrize(
    ("width", "height"),
    [(375, 812), (768, 1024), (1280, 800)],
    ids=["mobile", "tablet", "desktop"],
)
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_course_detail_does_not_overflow_the_viewport(
    live_server,
    live_server_site,
    mock_site_context,
    page: Page,
    width,
    height,
):
    """A long outline title truncates rather than pushing the detail page sideways.

    Browsed anonymously, so every outline row is locked and its title renders as
    plain text. The title span asks to truncate, but below ``lg`` the detail
    page's grid used to give it an implicit ``auto`` column, whose content-based
    minimum floored the whole column at the title's min-content width.
    """
    course = CourseFactory(
        title="Layout Course",
        slug="layout-course",
        access_config={"access_type": "free"},
    )
    ContentCollectionItemFactory(
        collection_object=course,
        child_object=TopicFactory(title=LONG_TOPIC_TITLE, slug="long-title-topic"),
        order=0,
    )

    page.set_viewport_size({"width": width, "height": height})
    page.goto(
        reverse_url(
            live_server,
            "learner_interface:course_detail",
            kwargs={"course_slug": course.slug},
        )
    )

    outline = page.get_by_role("navigation", name="Course outline")
    expect(outline.get_by_text(LONG_TOPIC_TITLE, exact=True)).to_be_attached()

    overflows = page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )

    assert overflows is False


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_long_outline_title_is_ellipsised_on_a_phone(
    live_server,
    live_server_site,
    mock_site_context,
    page: Page,
):
    """The mobile row fits because the title is clipped, not because it happened to fit.

    Without this the overflow test above could pass on a layout that merely
    dropped or wrapped the title.
    """
    course = CourseFactory(
        title="Layout Course",
        slug="layout-course",
        access_config={"access_type": "free"},
    )
    ContentCollectionItemFactory(
        collection_object=course,
        child_object=TopicFactory(title=LONG_TOPIC_TITLE, slug="long-title-topic"),
        order=0,
    )

    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(
        reverse_url(
            live_server,
            "learner_interface:course_detail",
            kwargs={"course_slug": course.slug},
        )
    )

    # The element carrying `truncate` is the one whose overflow is clipped, so
    # the assertion belongs on it rather than on the title text inside it.
    title_span = page.get_by_role("navigation", name="Course outline").locator(
        "span.truncate"
    )
    expect(title_span).to_have_count(1)
    assert title_span.evaluate("el => el.scrollWidth > el.clientWidth")
