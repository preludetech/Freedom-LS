import pytest
from playwright.sync_api import Page

from ..conftest import course_with_single_question_form, reverse_url


@pytest.mark.parametrize(
    ("width", "height"),
    [(375, 812), (768, 1024), (1280, 800)],
    ids=["mobile", "tablet", "desktop"],
)
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_option_rows_do_not_overflow_the_viewport(
    live_server, logged_in_page: Page, width, height
):
    """Option rows carry a selection indicator beside the option text. The row
    must still fit the viewport rather than pushing the page sideways.
    """
    course = course_with_single_question_form(
        "Option Layout Course", "option-layout-course", question_type="checkboxes"
    )
    logged_in_page.set_viewport_size({"width": width, "height": height})
    logged_in_page.goto(
        reverse_url(
            live_server,
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    overflows = logged_in_page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )

    assert overflows is False
